# NOTE: Do not bother keeping %changelog entries in this sample RPM spec

%if 0%{?rhel} && 0%{?rhel} <= 6
%{!?__python2: %global __python2 /usr/bin/python2}
%{!?python2_sitelib: %global python2_sitelib %(%{__python2} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%endif

Name:           InstantMirror
Version:        0.7
Release:        0%{?dist}
Summary:        Reverse Proxy Cache for Static HTTP Mirroring

Group:          System Environment/Daemons
License:        GPLv2+
URL:            https://github.com/opoplawski/InstantMirror
Source0:        InstantMirror-%{version}.tar.bz2

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
make install DESTDIR=$RPM_BUILD_ROOT
 
%files
%doc README.md TODO COPYING Changelog
%{python2_sitelib}/*
%config(noreplace) %{_sysconfdir}/httpd/conf.d/zz-InstantMirror.conf

%changelog
