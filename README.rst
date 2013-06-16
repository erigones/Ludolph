
Ludolph
#######

Monitoring Jabber Bot with support for `Zabbix <http://www.zabbix.com>`_.

Installation Notes
------------------

 - Install the latest version using pip::

    pip install https://github.com/erigones/Ludolph/tarball/master

 - Make sure all dependencies (listed below) are installed

 - Create and edit the config file::

    cp /usr/lib/python2.7/site-packages/ludolph/ludolph.cfg.example /etc/ludolph.cfg

 - The ``ludolph`` command should be installed somewhere in your ``PATH``.

 - Init scripts for Debian and RHEL based distributions are also available: https://github.com/erigones/Ludolph/tree/master/init.d


**Dependencies:**
 - sleekxmpp
 - dnspython (or dnspython3 when using Python 3)
 - tabulate


License
-------

For more informations see the LICENSE file.
