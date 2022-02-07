# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
# Copyright (c) 2022 Orion Poplawski <orion@nwra.com>
# Copyright (c) 2007 Arastra, Inc.

from webob import Request, Response
from webob.exc import HTTPError, HTTPGatewayTimeout, HTTPNotFound, HTTPTemporaryRedirect
from webob.static import FileApp
import base64
import http.client
import ssl
import urllib.request
import urllib.error
import urllib.parse
import os
import time
import calendar
import socket
import sys
import traceback
import errno
import fcntl

"""InstantMirror implements an automatically-populated mirror of static
documents from an upstream server.  It was originally developed for
mirroring a Fedora Linux tree and should work for any simple directory
tree of static files.

When a document request arrives, InstantMirror checks the last-modified
time of the document at the upstream server.  If the upstream copy is
newer than the local copy, or a local copy does not exist, it
downloads the document and stores it locally while serving it to the
client.  If the upstream copy cannot be found, either because it does
not exist or because the server is unreachable, the request is served
directly from the local mirror.  Directory indexes are always
requested from the upstream server, since they tend to change
frequently.

Superficially InstantMirror behaves like mod_disk_cache combined with
ProxyPass, except it maps the URL path directly to a local directory
rather than hashing the URL.  This allows the administrator to
pre-populate portions of the mirrored tree quickly, for example from a
DVD ISO acquired via BitTorrent.  InstantMirror makes certain
assumptions about how the upstream server provides directory indexes,
and does not deal with query strings (the part of the URL after the ?)
at all.
"""


def tryflock(f):
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except IOError as e:
        if e.errno == errno.EWOULDBLOCK:
            return False
        raise


class HTTPSClientAuthHandler(urllib.request.HTTPSHandler):
    def __init__(self, key, cert, context=None, cafile=None, capath=None):
        if cafile:
            context = ssl._create_stdlib_context(cert_reqs=ssl.CERT_REQUIRED,
                                                 cafile=cafile,
                                                 capath=capath)
        urllib.request.HTTPSHandler.__init__(self, context=context, check_hostname=True)
        self.key = key
        self.cert = cert

    def https_open(self, req):
        # Rather than pass in a reference to a connection class, we pass in
        # a reference to a function which, for all intents and purposes,
        # will behave as a constructor
        return self.do_open(self.getConnection, req, context=self._context,
                            check_hostname=self._check_hostname)

    def getConnection(self, host, **http_conn_args):
        return http.client.HTTPSConnection(host, key_file=self.key, cert_file=self.cert,
                                           **http_conn_args)


class MasterIterable(object):
    def __init__(self, input, output, local, mtime):
        self.input = input
        self.output = output
        self.local = local
        self.mtime = mtime

    def __iter__(self):
        return MasterIterator(self.input, self.output, self.local, self.mtime)

    def __del__(self):
        if os.path.exists(self.output.name):
            os.unlink(self.output.name)


class MasterIterator(object):
    chunk_size = 4096

    def __init__(self, input, output, local, mtime):
        self.input = input
        self.output = output
        self.local = local
        self.mtime = mtime

    def __iter__(self):
        return self

    def next(self):
        try:
            data = self.input.read(self.chunk_size)
            self.output.write(data)
        except Exception:
            # Something bad happened like a timeout or client closed connection, cleanup
            self.output.close()
            os.unlink(self.output.name)
            traceback.print_exc(file=sys.stderr)
            sys.stderr.flush()
            raise StopIteration
        if len(data) < 1:
            # Done reading input, move output into place
            self.output.close()
            if os.path.exists(self.local):
                os.unlink(self.local)
            try:
                os.rename(self.output.name, self.local)
            # We still get races and sometimes have two masters, at which point we probably
            # have a corrupt local file
            except OSError as e:
                if e.errno == errno.ENOENT:
                    if os.path.exists(self.local):
                        os.unlink(self.local)
                else:
                    raise
            else:
                os.utime(self.local, (self.mtime,) * 2)
            raise StopIteration
        return data

    __next__ = next  # py3 compat


class SlaveIterable(object):
    def __init__(self, file, clen):
        self.file = file
        self.clen = clen

    def __iter__(self):
        return SlaveIterator(self.file, self.clen)


class SlaveIterator(object):
    chunk_size = 4096

    def __init__(self, file, clen):
        self.file = file
        self.clen = clen
        self.pos = 0

    def __iter__(self):
        return self

    def next(self):
        # Stop when we have reached the expected size of the file
        if self.pos >= self.clen:
            raise StopIteration
        try:
            data = self.file.read(self.chunk_size)
        except IOError:
            raise StopIteration
        self.pos += len(data)
        # We will read 0 if at the end of the file, which might not be completed yet
        if len(data) == 0:
            # See if the master has gone away, and if so abort
            if tryflock(self.file):
                # TODO - This should be file=environ['wsgi.errors']
                print("InstantMirror: slave exiting at pos = %d" % (self.pos), file=sys.stderr)
                raise StopIteration
            # Sleep for a bit to avoid spinning
            time.sleep(0.01)
        return data

    __next__ = next  # py3 compat


def application(environ, start_response):
    req = Request(environ)

    local = environ['DOCUMENT_ROOT'] + req.path

    # Allow local mirror to set robots policy
    if req.path.endswith("/robots.txt"):
        if "InstantMirror.norobots" in environ:
            res = Response(status=200, body="User-agent: *\nDisallow: /\n")
            return res(environ, start_response)
        else:
            # Use local robots.txt if it exists
            if os.path.exists(local):
                return FileApp(local)(environ, start_response)
            else:
                return HTTPNotFound()(environ, start_response)

    # Treat .rpm files as immutable, serve it if it exists
    if req.path.endswith(".rpm") and os.path.exists(local):
        return FileApp(local)(environ, start_response)

    # Setup client SSL if needed
    if 'InstantMirror.cert' in environ:
        cert_handler = HTTPSClientAuthHandler(environ['InstantMirror.key'],
                                              environ['InstantMirror.cert'],
                                              cafile=environ['InstantMirror.cacert'])
        opener = urllib.request.build_opener(cert_handler)
        urllib.request.install_opener(opener)

    # Open the upstream URL and get the headers
    try:
        upstream = environ["InstantMirror.upstream"] + \
            req.path.replace("/index.html", "/")
        upreq = urllib.request.Request(upstream)
        if 'InstantMirror.username' in environ:
            base64string = base64.encodestring('%s:%s' % (environ['InstantMirror.username'],
                                                          'null')).replace('\n', '')
            upreq.add_header("Authorization", "Basic %s" % base64string)
        reqrange = None
        # Pass along headers like "Accept", but not:
        #  "Accept-Encoding" which can change the file format
        #  "If-*" wich can possibly return nothing
        #  "Host" which will be us
        for header in req.headers:
            if header in ['Accept', 'Content-Type', 'User-Agent']:
                upreq.add_header(header, req.headers.get(header))
            # Range requests need special handling
            if header == 'Range':
                reqrange = req.headers.get(header)
                upreq.add_header(header, reqrange)
        if 'InstantMirror.cacert' in environ:
            o = opener.open(upreq, timeout=10)
        else:
            o = urllib.request.urlopen(upreq, timeout=10)
        if 'Last-Modified' in o.headers:
            mtime = calendar.timegm(time.strptime(o.headers['Last-Modified'],
                                                  '%a, %d %b %Y %H:%M:%S GMT'))
        else:
            mtime = calendar.timegm(time.gmtime())
        clen = o.headers.get("Content-Length")
        crange = o.headers.get("Content-Range")
        isdir = o.url.endswith("/")
    except urllib.error.HTTPError as e:
        print("InstantMirror status: %s" % e.code, file=environ['wsgi.errors'])
        print("InstantMirror info: %s" % e.info(), file=environ['wsgi.errors'])
        print("InstantMirror reponse: %s" % e.read(), file=environ['wsgi.errors'])
        exc = HTTPError()
        # TODO - This doesn't work to change exc
        exc.code = e.code
        exc.detail = e.info
        return exc(environ, start_response)
    except urllib.error.URLError as e:
        # Handle timeouts
        if type(e) == socket.timeout:
            return HTTPGatewayTimeout()(environ, start_response)
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        exc = HTTPError()
        return exc(environ, start_response)
    except Exception:
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        return HTTPError()(environ, start_response)

    if isdir:
        # If the upstream URL ends with /, we assume it's a directory and
        # store the local file as index.html
        if not req.path.endswith("/") and not req.path.endswith("/index.html"):
            redir = "http://" + environ['SERVER_NAME'] + req.path + "/"
            print("InstantMirror: redirect to %s" % redir, file=environ['wsgi.errors'])
            exc = HTTPTemporaryRedirect(location=redir)
            return exc(environ, start_response)

        if not req.path.endswith("/index.html"):
            local = os.path.join(local, "index.html")

    dir = os.path.dirname(local)
    # Try to avoid creating an already existing directory
    if not os.path.exists(dir):
        # But we can still have races, so handle the error gracefully
        try:
            os.makedirs(dir)
        except OSError as e:
            if e.errno == errno.EEXIST:
                pass
            else:
                raise
    # If the local file exists and is up-to-date, serve it to the client
    if not isdir and os.path.exists(local):
        stat = os.stat(local)
        if int(stat.st_mtime) == mtime:
            # and (clen is None or stat.st_size == clen):
            print("InstantMirror: %s is up to date %d" % (local, mtime),
                  file=environ['wsgi.errors'])
            return FileApp(local)(environ, start_response)

    # We are about to download the upstream URL and copy to the client; set up
    # relevant headers
    response_headers = []
    # Copy some upstream headers to the response
    for header in ['Content-Type', 'ETag']:
        if header in o.headers:
            response_headers.append((header, o.headers[header]))
    if clen:
        response_headers.append(("Content-Length", clen))
    else:
        clen = 0

    # If a range was requested, just return that but don't write anything to disk
    if reqrange:
        if crange:
            response_headers.append(("Content-Range", crange))
        body = bytearray()
        while True:
            data = o.read(4096)
            if len(data) < 1:
                break
            try:
                body.extend(data)
            except IOError:
                break
        res = Response(status=206, headerlist=response_headers, body=bytes(body))
        res.last_modified = mtime
        return res(environ, start_response)

    # Download and serve file
    f = open("%s.tmp.%x" % (local, hash(local)), "ab+", 4096)
    # Start at the beginning if already being written to
    f.seek(0)

    # This bit of complicated goop lets us optimize the case where
    # another instance of InstantMirror.py is already downloading the
    # URL from upstream: the other instance acts as the master,
    # appending data to the local file; we act as a slave, copying data
    # from the local file to our client.  Unfortunately this
    # implementation is pretty lame and the slave is throttled by the
    # download speed of the master's client.
    if tryflock(f):
        print("InstantMirror: master on %s.tmp.%x, clen = %d, mtime = %d" % (
            local, hash(local), int(clen), mtime), file=environ['wsgi.errors'])
        # Master
        app_iter = MasterIterable(o, f, local, mtime)
    else:
        print("InstantMirror: slave on %s.tmp.%x, clen = %d" % (
            local, hash(local), int(clen)), file=environ['wsgi.errors'])
        # We are the slave, read from the file
        app_iter = SlaveIterable(f, int(clen))

    res = Response(status=200, headerlist=response_headers, app_iter=app_iter)
    res.last_modified = mtime
    return res(environ, start_response)
