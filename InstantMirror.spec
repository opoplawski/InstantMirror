Name:           InstantMirror
Version:        0.9
Release:        1%{?dist}
Summary:        Reverse Proxy Cache for Static HTTP Mirroring

Group:          System Environment/Daemons
License:        GPLv2+
URL:            https://github.com/opoplawski/InstantMirror
Source0:        https://github.com/opoplawski/InstantMirror/archive/%{version}/%{name}-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  python2-devel

Requires:       mod_python

%description
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

%prep
%setup -q

%install
%make_install
 
%files
%doc README.md TODO COPYING
%{python2_sitelib}/*
%config(noreplace) %{_sysconfdir}/httpd/conf.d/InstantMirror.conf

%changelog
* Thu Feb 11 2021 Orion Poplawski 0.9-1
- Update to 0.9

* Mon May  6 2019 Orion Poplawski 0.8-1
- Update to 0.8

* Tue Mar 17 2015 Orion Poplawski 0.7-1
- Update to current running version

* Thu Aug 23 2012 Orion Poplawski 0.6-1
- Update to current running version

* Thu Jun 25 2009 Orion Poplawski 0.5-1
- Update to current running version
