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
import errno, fcntl, select

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
      o = urllib2.urlopen(upreq, timeout=5)
      mtime = calendar.timegm(o.headers.getdate("Last-Modified") or time.gmtime())
      ctype = o.headers.get("Content-Type")
      clen = o.headers.get("Content-Length")
      crang = o.headers.get("Content-Range")
      isdir = o.url.endswith("/")
   except:
      traceback.print_exc(file=sys.stderr)
      sys.stderr.flush
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
   if crang:
      req.headers_out["Content-Range"] = crang
      req.status = mod_python.apache.HTTP_PARTIAL_CONTENT
   req.headers_out["Last-Modified"] = rfc822.formatdate(mtime)

   if not crang:
      f = file("%s.tmp.%x" % (local, hash(local)), "a+")

      # This bit of complicated goop lets us optimize the case where
      # another instance of InstantMirror.py is already downloading the
      # URL from upstream: the other instance acts as the master,
      # appending data to the local file; we act as a slave, copying data
      # from the local file to our client.  Unfortunately this
      # implementation is pretty lame and the slave is throttled by the
      # download speed of the master's client.
      pos = 0
      while True:
         select.select([f], [], [], 1)
         if tryflock(f):
            # If we can flock the local file, then the master must have
            # gone away; so we become the master
            break
         else:
            # The master still running: copy local data to client
            data = f.read(1024)
            req.write(data)
            pos += len(data)

      # Master mode: download the upstream URL, store data locally and
      # copy data to the client
      if pos > 0:
         # If we have already copied some data to the client as a slave,
         # we must either trash the first pos bytes of the upstream URL
         # or re-request it with Range: pos- before continuing to append
         # to the local file and copy data to the client.  Since that
         # would require work and we're lazy, we just give up and let the
         # client retry the whole download.
         f.close()
         return mod_python.apache.OK
      f.seek(pos)
      f.truncate()

   while True:
      data = o.read(1024)
      if len(data) < 1:
         break
      req.write(data)
      if not crang:
         f.write(data)

   if not crang:
      if os.path.exists(local):
         os.unlink(local)
      os.rename(f.name, local)
      os.utime(local, (mtime,) * 2)
      f.close()

   return mod_python.apache.OK
