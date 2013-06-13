Ludolph
#######

Monitoring Jabber Bot

Installation Notes
------------------

 - Install the latest version by using pip::

    pip install https://github.com/ricco386/Ludolph/tarball/master

 - Make sure all dependencies (listed below) are installed.

 - Create and edit the config file::

    cp /usr/lib/python2.7/site-packages/ludolph/ludolph.cfg.example /etc/ludolph.cfg

 - The ludolph command should be already installed somewhere in ``PATH``. Or an init script for Debian and RHEL based distributions is available somewhere in your installation prefix (probably: ``/usr/lib/python2.7/site-packages/ludolph/``).


**Dependencies:**
 - sleekxmpp
 - dnspython


License
-------

For more informations see the LICENSE file.
