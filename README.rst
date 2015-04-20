Ludolph
#######

Monitoring Jabber Bot with `Zabbix <http://www.zabbix.com>`_ support.

.. image:: https://badge.fury.io/py/ludolph.png
    :target: http://badge.fury.io/py/ludolph

Features
--------

* Simple and modular design
* Alerts from Zabbix
* Multi-User Chat (XEP-0045)
* Colorful messages (XEP-0071)
* Avatars (XEP-0084)
* Roster management and ACL configuration
* Plugins and commands::

 * ludolph.plugins.zabbix *
    * ack - acknowledge event with optional note
    * alerts - show a list of current zabbix alerts
    * duty - show a list of users in duty user group
    * groups - show a list of host groups
    * hosts - show a list of hosts
    * outage - show, create or delete maintenance periods
    * zabbix-version - show version of Zabbix API

 * ludolph.plugins.base *
    * about - details about this project
    * avatar-list - list available avatars for Ludolph (admin only)
    * avatar-set - set avatar for Ludolph (admin only)
    * broadcast - sent private message to every user in roster (admin only)
    * help - show this help
    * muc-invite - invite user to multi-user chat room (admin only)
    * roster-list - list of users on Ludolph's roster (admin only)
    * roster-remove - remove user from Ludolph's roster (admin only)
    * shutdown - shutdown Ludolph bot
    * uptime - show Ludolph uptime
    * version - display Ludolph version


Installation
------------

- Install the latest released version using pip::

    pip install ludolph

- Make sure all dependencies (listed below) are installed (done automatically when installing via pip)

- Create and edit the configuration file::

    cp /usr/lib/python2.7/site-packages/ludolph/ludolph.cfg.example /etc/ludolph.cfg

- The ``ludolph`` command should be installed somewhere in your ``PATH``.

- Init scripts for Debian and RHEL based distributions are also available: https://github.com/erigones/Ludolph/tree/master/init.d


**Dependencies:**

- `zabbix-api-erigones <https://github.com/erigones/zabbix-api/>`_ (1.0+)
- `dnspython <http://www.dnspython.org/>`_ (1.10.0+) (or dnspython3 when using Python 3)
- `sleekxmpp <http://sleekxmpp.com/>`_ (1.1.11+)
- `bottle <http://bottlepy.org/>`_ (0.12.7+)


Links
-----

- Wiki: https://github.com/erigones/Ludolph/wiki
- Bug Tracker: https://github.com/erigones/Ludolph/issues
- Twitter: https://twitter.com/erigones


License
-------

For more information see the `LICENSE <https://github.com/erigones/Ludolph/blob/master/LICENSE>`_ file.

Avatars have been designed by `Freepik.com <http://www.freepik.com>`_.

####

The Zabbix plugin is inspired by `Dante <http://www.digmia.com>`_.
