# NOTE: Do not bother keeping %changelog entries in this sample RPM spec

%{!?python_sitelib: %define python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}

Name:           InstantMirror
Version:        0.2
Release:        0%{?dist}
Summary:        Reverse Proxy Cache for Static HTTP Mirroring

Group:          System Environment/Daemons
License:        GPLv2+
URL:            https://hosted.fedoraproject.org/projects/InstantMirror
Source0:        InstantMirror-%{version}.tar.bz2
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

BuildArch:      noarch
BuildRequires:  python-devel

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

%build
echo "Nothing to build."

%install
rm -rf $RPM_BUILD_ROOT
make install DESTDIR=$RPM_BUILD_ROOT
 
%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root,-)
%doc README TODO COPYING Changelog
%{python_sitelib}/*
%config(noreplace) %{_sysconfdir}/httpd/conf.d/InstantMirror.conf

%changelog
