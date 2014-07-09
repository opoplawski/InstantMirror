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
# Copyright (c) 2007 Arastra, Inc.

import mod_python, mod_python.util, urllib2, os, shutil, time, calendar
import rfc822, string, sys, traceback
import errno, fcntl

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
   except IOError, e:
      if e.errno == errno.EWOULDBLOCK:
         return False
      raise

def handler(req):
   #if req.uri.endswith("/index.html") or req.uri.endswith("/"):
   #   return mod_python.apache.DECLINED

   # Open the upstream URL and get the headers
   try:
      upstream = req.get_options()["InstantMirror.upstream"] + req.uri
      upreq = urllib2.Request(upstream)
      if req.headers_in.has_key('Range'):
         upreq.add_header('Range', req.headers_in.get('Range'))
      o = urllib2.urlopen(upreq, timeout=10)
      mtime = calendar.timegm(o.headers.getdate("Last-Modified") or time.gmtime())
      ctype = o.headers.get("Content-Type")
      clen = o.headers.get("Content-Length")
      crang = o.headers.get("Content-Range")
      isdir = o.url.endswith("/")
   except urllib2.HTTPError as e:
      req.status = e.code
      return mod_python.apache.OK
   except urllib2.URLError as e:
      # Handle timeouts
      if type(e) == socket.timeout:
         req.status = mod_python.apache.HTTP_REQUEST_TIME_OUT
         return mod_python.apache.OK
      traceback.print_exc(file=sys.stderr)
      sys.stderr.flush()
      return mod_python.apache.DECLINED
   except:
      traceback.print_exc(file=sys.stderr)
      sys.stderr.flush()
      return mod_python.apache.DECLINED

   local = req.document_root() + req.uri
   if isdir:
      # If the upstream URL ends with /, we assume it's a directory and
      # store the local file as index.html
      if not req.uri.endswith("/"):
         mod_python.util.redirect(req, "http://" + req.server.server_hostname
                                  + req.uri + "/")
      local = os.path.join(local, "index.html")
      
   dir = os.path.dirname(local)
   if not os.path.exists(dir):
      os.makedirs(dir)
   # If the local file exists and is up-to-date, serve it to the client
   if not isdir and os.path.exists(local) and int(os.stat(local).st_mtime) == mtime:
      return mod_python.apache.DECLINED

   # We are about to download the upstream URL and copy to the client; set up
   # relevant headers
   if ctype:
      req.content_type = ctype
   if clen:
      req.headers_out["Content-Length"] = clen
   else:
      clen = 0
   req.headers_out["Last-Modified"] = rfc822.formatdate(mtime)
   if crang:
      req.headers_out["Content-Range"] = crang
      req.status = mod_python.apache.HTTP_PARTIAL_CONTENT
      while True:
         data = o.read(4096)
         if len(data) < 1:
            break
         req.write(data)
   else:
      f = open("%s.tmp.%x" % (local, hash(local)), "a+", 4096)
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
         sys.stderr.write("InstantMirror: master on %s.tmp.%x, clen = %d\n" % (local, hash(local), int(clen)))
         sys.stderr.flush()
         # Master mode: download the upstream URL, store data locally and
         # copy data to the client
         while True:
            data = o.read(4096)
            if len(data) < 1:
               break
            req.write(data)
            f.write(data)
         f.close()
         if os.path.exists(local):
            os.unlink(local)
         os.rename(f.name, local)
         os.utime(local, (mtime,) * 2)
      else:
         sys.stderr.write("InstantMirror: slave on %s.tmp.%x, clen = %d\n" % (local, hash(local), int(clen)))
         sys.stderr.flush()
         # We are the slave, read from the file
         pos = 0
         while pos < int(clen):
            data = f.read(4096)
            req.write(data)
            pos += len(data)
            # We will read 0 if at the end of the file, which might not be completed yet
            if len(data) == 0:
               # See if the master has gone away, and if so abort
               if tryflock(f):
                  sys.stderr.write("InstantMirror: slave exiting at pos = %d, clen = %d\n" % (pos, int(clen)))
                  sys.stderr.flush()
                  break
               # Sleep for a bit to avoid spinning
               time.sleep(0.01)
         f.close()

   return mod_python.apache.OK
