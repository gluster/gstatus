Name:		gstatus
Version:	0.63
Release:	2%{?dist}
Summary:	Show the current health of the elements in a Gluster Trusted Pool

Group:		Applications/System
License:	GPLv3
URL:		https://forge.gluster.org/gstatus

# download from https://forge.gluster.org/gstatus/gstatus/archive-tarball/v%{version}
# rename to gstatus-%{version}.tar.gz

Source0:	%{name}-%{version}.tar.gz
BuildRoot:	%(mktemp -ud %{_tmppath}/%{name}-%{version}-%{release}-XXXXXX)

BuildRequires:	python2-devel
BuildRequires:	python-setuptools

Requires:	/usr/sbin/gluster
Requires:	glusterfs >= 3.4

%if 0%{?rhel} && 0%{?rhel} <= 6
%{!?__python2: %global __python2 /usr/bin/python2}
%{!?python2_sitelib: %global python2_sitelib %(%{__python2} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%{!?python2_sitearch: %global python2_sitearch %(%{__python2} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib(1))")}
%endif

%description
CLI command to provide a status check on the cluster’s health, providing
a view of node, volume state (up, degraded, partial or down), brick 
up/down states and capacity information by volume (usable, used).

In addition to the interactive model, a json or keyvalue output option 
is also available through '-o json|keyvalue'. By utilising -o, you can 
log the state of the cluster to a file, and interpret with Splunk, 
Logstash or nagios/zabbix.

Errors detected, are listed in plain english together and provide an
easy way to assess the impact to a service, based on a disruptive event 
within the trusted pool (cluster).

%prep
%setup -q -n %{name}


%build
CFLAGS="$RPM_OPT_FLAGS" %{__python} setup.py build


%install
rm -rf %{buildroot}
%{__python} setup.py install --skip-build --root %{buildroot} --install-scripts %{_bindir}


%clean
rm -rf %{buildroot}


%files
%defattr(-,root,root,-)
%doc README examples
%{_bindir}/gstatus
%{python2_sitelib}/gstatus/
%{python2_sitelib}/gstatus-%{version}-*.egg-info/


%changelog
* Mon Mar 02 2015 Paul Cuzner <pcuzner@redhat.com> 0.63-2
- minor update removing the dependency on python-netifaces module
* Mon Jan 12 2015 Paul Cuzner <pcuzner@redhat.com> 0.63
- switch defineNodes method from "gluster peer status" to "gluster pool list"
- added timeout threshold to all gluster commands used
- added timeout option for the user to tweak (-t)
- now identifies an active peer for all commands, so local gluster can be down

* Thu Nov 13 2014 Paul Cuzner <pcuzner@redhat.com> 0.62-1
- fix product name format

* Tue Sep 30 2014 Paul Cuzner <pcuzner@redhat.com> 0.62
- fix - capacity calculations, and formating
- fix - self heal status calucation corrected
- fix - corrected client counts excluding rhs nodes
- fix - node names can now resolv with /etc/hosts entries
- added - snapshot counts at cluster and volume level
- added - active tasks information by volume
- added - snapshot information to json/keyvalue output modes
- added - product name added to output
- added - self heal daemon checks to health checks
- added - '-w' option to turn off interactive progress messages
- maintenance - added brX and ibX interfaces to network code for name/IP resolution (Stephan Holljes)
- maintenance - moved glfsversion to separate module
- maintenance - added snapshot class to track snapshot attributes
- maintenance - '-b' now needed to query selfheal state, reducing typical run time

* Tue Aug 12 2014 Paul Cuzner <pcuzner@redhat.com> 0.60.1
- minor fix for cluster capacity calculation

* Mon Aug 11 2014 Paul Cuzner <pcuzner@redhat.com> 0.60
- refactor the node definition logic (now based on uuid not name)
- fix - supports cluster defined on fqdn and volumes using shortnames and IP based clusters
- fix - corrected cluster capacity calculations when brick(s) used by multiple volumes
- added capacity overcommit flag if the same device is referenced by multiple bricks
- added overcommit status field added to output (console,keyvalue,json)
- added volume stats to json output mode  
- added info message when bricks are missing to confirm the capacity info is inaccurate
- added -n option to skip self heal info gathering
- misc doc updates and refresh of examples directory

* Mon Jun 23 2014 Paul Cuzner  <pcuzner@redhat.com> 0.5-6.0
- Added -D debug option for problem analysis
- config module added for global vars across modules
- added code to allow for arbitration nodes in the trusted pool
- added product name (RHS version or Community version) to -o output
- fix - workaround added for silent failure of gluster vol status clients

* Wed Apr 2 2014 Paul Cuzner  <pcuzner@redhat.com> 0.5-0.1
- updated to account for fqdn cluster definitions 

* Mon Mar 24 2014 Paul Cuzner  <pcuzner@redhat.com> 0.5-0.1
- Update to version 0.5

* Thu Mar 20 2014 Niels de Vos <ndevos@redhat.com> 0.45-0.1
- Update to version 0.45

* Mon Mar 3 2014 Niels de Vos <ndevos@redhat.com> - 0.3-0.2
- Fix building in mock, add BuildRequires python-setuptools

* Mon Mar 3 2014 Niels de Vos <ndevos@redhat.com> - 0.3-0.1
- Initial packaging
