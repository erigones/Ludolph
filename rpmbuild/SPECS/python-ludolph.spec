%global pypi_name ludolph

Name:           python-%{pypi_name}
Version:        1.0.1
Release:        1%{?dist}
Summary:        Monitoring Jabber Bot

License:        BSD
URL:            https://github.com/erigones/Ludolph/
Source0:        https://files.pythonhosted.org/packages/source/l/%{pypi_name}/%{pypi_name}-%{version}.tar.gz
BuildArch:      noarch
 
BuildRequires:  python2-devel
BuildRequires:  python2-setuptools
BuildRequires:  systemd

BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
BuildRequires:  systemd

%description
Monitoring Jabber Bot with Zabbix support, completely written in Python.

Features
* Simple and modular design
* Alerts from Zabbix
* Multi-User Chat (XEP-0045)
* Colorful messages (XEP-0071)
* Attention (XEP-0224)
* Avatars (XEP-0084)
* Roster management and ACL configuration
* Webhooks and Cron jobs
* Plugins and commands


%package -n     python2-%{pypi_name}
Summary:        %{summary}
%{?python_provide:%python_provide python2-%{pypi_name}}
 
Requires:       python2-sleekxmpp
Requires:       python2-bottle
Requires:       python2-dns
Requires:       systemd
%description -n python2-%{pypi_name}
Monitoring Jabber Bot with Zabbix support, completely written in Python.

Features
* Simple and modular design
* Alerts from Zabbix
* Multi-User Chat (XEP-0045)
* Colorful messages (XEP-0071)
* Attention (XEP-0224)
* Avatars (XEP-0084)
* Roster management and ACL configuration
* Webhooks and Cron jobs
* Plugins and commands


%package -n     python3-%{pypi_name}
Summary:        %{summary}
%{?python_provide:%python_provide python3-%{pypi_name}}
 
Requires:       python3-sleekxmpp
Requires:       python3-bottle
Requires:       python3-dns
Requires:       systemd
%description -n python3-%{pypi_name}
Monitoring Jabber Bot with Zabbix support, completely written in Python.

Features
* Simple and modular design
* Alerts from Zabbix
* Multi-User Chat (XEP-0045)
* Colorful messages (XEP-0071)
* Attention (XEP-0224)
* Avatars (XEP-0084)
* Roster management and ACL configuration
* Webhooks and Cron jobs
* Plugins and commands


%prep
%autosetup -n %{pypi_name}-%{version}
# Remove bundled egg-info
rm -rf %{pypi_name}.egg-info

%build
%py2_build
%py3_build

%install
%py2_install
# Make sure we clean up everything after python2 build
rm %{buildroot}/%{_bindir}/*

%py3_install

install -p -D -m 644 init.d/ludolph.service %{buildroot}%{_unitdir}/ludolph.service

%post
%systemd_post ludolph.service

%preun
%systemd_preun ludolph.service

%postun
%systemd_postun ludolph.service

%files -n python2-%{pypi_name}
%license LICENSE
%doc README.rst
%ghost %config(noreplace) %{_sysconfdir}/ludolph.cfg
%{_unitdir}/ludolph.service
%{python2_sitelib}/%{pypi_name}
%{python2_sitelib}/%{pypi_name}-%{version}-py?.?.egg-info

%files -n python3-%{pypi_name}
%license LICENSE
%doc README.rst
%{_bindir}/ludolph
%ghost %config(noreplace) %{_sysconfdir}/ludolph.cfg
%{_unitdir}/ludolph.service
%{python3_sitelib}/%{pypi_name}
%{python3_sitelib}/%{pypi_name}-%{version}-py?.?.egg-info

%changelog
* Mon Aug 21 2017 Richard Kellner <richard.kellner@gmail.com> - 1.0.1-1
- Initial rpm package for Ludolph version 1.0.1
