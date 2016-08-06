Ludolph
#######

Monitoring Jabber Bot with `Zabbix <http://www.zabbix.com>`_ support, completely written in Python.

.. image:: https://badge.fury.io/py/ludolph.png
    :target: http://badge.fury.io/py/ludolph

Features
--------

* `Simple and modular design <https://github.com/erigones/Ludolph/wiki/How-to-create-a-plugin>`_
* `Alerts from Zabbix <https://github.com/erigones/Ludolph/wiki/How-to-configure-Zabbix-to-work-with-Ludolph>`_
* Multi-User Chat (XEP-0045)
* Colorful messages (XEP-0071)
* Attention (XEP-0224)
* `Avatars (XEP-0084) <https://github.com/erigones/Ludolph/wiki/F.A.Q.#how-to-set-an-avatar>`_
* `Roster management and ACL configuration <https://github.com/erigones/Ludolph/wiki/User-subscription-management>`_
* `Webhooks and cron jobs <https://github.com/erigones/Ludolph/wiki/Webhooks-and-cron-jobs>`_
* `Plugins and commands <https://github.com/erigones/Ludolph/wiki/Plugins>`_::

    * ludolph.plugins.zabbix
        * ack - acknowledge event with optional note
        * alerts - show a list of current or previous zabbix alerts
        * duty - show a list of users in duty user group
        * groups - show a list of host groups
        * hosts - show a list of hosts
        * outage - show, create or delete maintenance periods
        * zabbix-version - show version of Zabbix API

    * ludolph.plugins.base
        * about - details about this project
        * at - list, add, or delete jobs for later execution
        * attention - send XMPP attention to user/room
        * avatar - list available avatars or set an avatar for Ludolph (admin only)
        * broadcast - sent private message to every user in roster (admin only)
        * help - show this help
        * message - send new XMPP message to user/room
        * remind - list, add, or delete reminders
        * roster - list and manage users on Ludolph's roster (admin only)
        * status - set Ludolph's status (admin only)
        * uptime - show Ludolph uptime
        * version - display version of Ludolph or registered plugin

    * ludolph.plugins.muc
        * invite - invite user or yourself to multi-user chat room (room admin only)
        * kick - kick user from multi-user chat room (room admin only)
        * motd - show, set or remove message of the day
        * topic - set room subject (room admin only)

    * ludolph.plugins.commands
        * os-uptime - display system uptime


Installation
------------

- Install the latest released version using pip::

    pip install ludolph

 - Or install the latest development version::

    pip install https://github.com/erigones/ludolph/zipball/master

- Make sure all dependencies (listed below) are installed (done automatically when installing via pip)

- Create and edit the configuration file::

    cp /usr/lib/python2.7/site-packages/ludolph/ludolph.cfg.example /etc/ludolph.cfg

- The ``ludolph`` command should be installed somewhere in your ``PATH``.

- Init scripts for Debian and RHEL based distributions are also available: https://github.com/erigones/Ludolph/tree/master/init.d

See `the complete install guide <https://github.com/erigones/Ludolph/wiki/How-to-install-and-configure-Ludolph>`_ and `Zabbix integration guide <https://github.com/erigones/Ludolph/wiki/How-to-configure-Zabbix-to-work-with-Ludolph>`_ for more info.


**Dependencies:**

- `ludolph-zabbix <https://github.com/erigones/ludolph-zabbix/>`_ (1.5+)
- `dnspython <http://www.dnspython.org/>`_ (1.13.0+)
- `sleekxmpp <http://sleekxmpp.com/>`_ (1.1.11+)
- `bottle <http://bottlepy.org/>`_ (0.12.7+)


Links
-----

- Wiki: https://github.com/erigones/Ludolph/wiki
- Bug Tracker: https://github.com/erigones/Ludolph/issues
- Contribution guide: https://github.com/erigones/Ludolph/wiki/Contribution-guide
- Google+ Community: https://plus.google.com/u/0/communities/112192048027134229675
- Twitter: https://twitter.com/erigones


License
-------

For more information see the `LICENSE <https://github.com/erigones/Ludolph/blob/master/LICENSE>`_ file.

Avatars have been designed by `Freepik.com <http://www.freepik.com>`_.
