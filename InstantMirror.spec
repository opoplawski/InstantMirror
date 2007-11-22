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
Reverse Proxy Cache for Static HTTP Mirroring
This package allows instant creation of HTTP mirror of static HTTP content 
through a reverse proxy cache.  Cached files are conveniently stored in their
original directory structure and filenames on the local filesystem.

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
