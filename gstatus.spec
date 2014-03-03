Name:		gstatus
Version:	0.3
Release:	0.1%{?dist}
Summary:	Show the current health of the elements in a Gluster Trusted Pool

Group:		Applications/System
License:	GPLv3
URL:		https://forge.gluster.org/gstatus
Source0:	https://forge.gluster.org/gstatus/gstatus/archive-tarball/v%{version}#/%{name}-%{version}.tar.gz
BuildRoot:	%(mktemp -ud %{_tmppath}/%{name}-%{version}-%{release}-XXXXXX)

BuildRequires:	python2-devel
Requires:	/usr/sbin/gluster
Requires:	glusterfs >= 3.4

%if 0%{?rhel} && 0%{?rhel} <= 6
%{!?__python2: %global __python2 /usr/bin/python2}
%{!?python2_sitelib: %global python2_sitelib %(%{__python2} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%{!?python2_sitearch: %global python2_sitearch %(%{__python2} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib(1))")}
%endif

%description
CLI command to provide a status check on the cluster’s health, providing a view
of node, volume and brick up/down states, volume status (online, degraded etc)
and capacity information by volume (usable, used).

Errors detected, will be listed in plain english with the potential to extend
to write the output in xml form for integration with automated checks.


%prep
%setup -q


%build
CFLAGS="$RPM_OPT_FLAGS" %{__python} setup.py build


%install
rm -rf %{buildroot}
%{__python} setup.py install --skip-build --root %{buildroot} --install-scripts %{_sbindir}


%clean
rm -rf %{buildroot}


%files
%defattr(-,root,root,-)
%doc README examples
%{_sbindir}/gstatus
%{python2_sitelib}/gstatus/
%{python2_sitelib}/gstatus-%{version}-*.egg-info/


%changelog
* Mon Mar 3 2014 Niels de Vos <ndevos@redhat.com> - 0.3-0.1
- Initial packaging
