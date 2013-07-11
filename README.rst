Ludolph
#######

Monitoring Jabber Bot with `Zabbix <http://www.zabbix.com>`_ support

Installation Notes
------------------

 - Install the latest released version using pip::

    pip install ludolph

 - Make sure all dependencies (listed below) are installed (done automatically when installing via pip)

 - Create and edit the configuration file::

    cp /usr/lib/python2.7/site-packages/ludolph/ludolph.cfg.example /etc/ludolph.cfg

 - The ``ludolph`` command should be installed somewhere in your ``PATH``.

 - Init scripts for Debian and RHEL based distributions are also available: https://github.com/erigones/Ludolph/tree/master/init.d


**Dependencies:**
 - sleekxmpp (1.1.11+)
 - dnspython (1.10.0+) (or dnspython3 when using Python 3)
 - tabulate (0.4.4+)


Links
-----

 - Wiki: https://github.com/erigones/Ludolph/wiki
 - Bug Tracker: https://github.com/erigones/Ludolph/issues
 - Twitter: https://twitter.com/erigones


License
-------

For more information see the LICENSE file
