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

import mod_python, mod_python.util, urllib, os, shutil, time, calendar, rfc822, errno, fcntl, select

"""InstantMirror implements an automatically-populated mirror of static
documents from an upstream server.  It was originally developed for
mirroring a Fedora Linux tree and should work for any simple directory
tree of static files.

When a document request arrives, InstantMirror checks the last-modified
time of the document at the upstream server.  If the upstream copy is
newer than the local copy, or a local copy does not exist, it
downloads the document and stores it locally before serving it to the
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

To configure a Fedora Linux mirror for a virtual host
mirrors.sample.com, add something like this to httpd.conf:

<VirtualHost *:80>
   ServerName mirrors.sample.com
   ServerName mirrors
   DocumentRoot /mirrors

   SetHandler mod_python
   PythonHandler InstantMirror
   PythonDebug on
   PythonOption InstantMirror.upstream http://download.fedora.redhat.com
</VirtualHost>

Ensure mod_python is installed and enabled, and that /mirrors is
writable by the apache user.
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
   if req.uri.endswith("/index.html"):
      return mod_python.apache.DECLINED

   try:
      upstream = req.get_options()["InstantMirror.upstream"] + req.uri
      o = urllib.urlopen(upstream)
      mtime = calendar.timegm(o.headers.getdate("Last-Modified") or time.gmtime())
      ctype = o.headers.get("Content-Type")
      clen = o.headers.get("Content-Length")
      isdir = o.url.endswith("/")
   except:
      return mod_python.apache.DECLINED

   local = req.document_root() + req.uri
   if isdir:
      if not req.uri.endswith("/"):
         mod_python.util.redirect(req, "http://" + req.server.server_hostname
                                  + req.uri + "/")
      local = os.path.join(local, "index.html")
      
   dir = os.path.dirname(local)
   if not os.path.exists(dir):
      os.makedirs(dir)
   if not isdir and os.path.exists(local) and os.stat(local).st_mtime >= mtime:
      return mod_python.apache.DECLINED

   if ctype:
      req.content_type = ctype
   if clen:
      req.headers_out["Content-Length"] = clen
   req.headers_out["Last-Modified"] = rfc822.formatdate(mtime)

   f = file("%s.tmp.%x" % (local, hash(local)), "a+")
   pos = 0
   while True:
      select.select([f], [], [], 1)
      if tryflock(f):
         # switch to master mode
         break
      else:
         # master still running: copy local data to client
         data = f.read(1024)
         req.write(data)
         pos += len(data)
   if pos == 0:
      # master mode: download file, store data locally and copy to client
      f.seek(0)
      f.truncate()
      while True:
         data = o.read(1024)
         if len(data) < 1:
            break
         req.write(data)
         f.write(data)
      if os.path.exists(local):
         os.unlink(local)
      os.rename(f.name, local)
      os.utime(local, (mtime,) * 2)
   f.close()
   return mod_python.apache.OK
