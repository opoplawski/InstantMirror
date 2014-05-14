Instantly create a HTTP mirror of remote static HTTP content.

For example, you can instantly create a Fedora mirror on your local network.
Files that you download from your mirror are downloaded from an upstream web
server, passed to your client as it arrives, then stored on the server when
the download is complete.  Subsequent downloads of that same file are served
from the cache directory, quick and efficient.

Cached files are conveniently stored in their original directory structure and
filenames on the server filesystem.  This allows flexibility to do things like:
 - use rsync on the very same directory structure to fully populate the cache
 - serve the tree over other protocols like NFS
