Ludolph
#######

Zabbix monitoring Jabber bot

Installation Notes
------------------

Installation have to be done as root. Download the latest release from 
`Github <https://github.com/ricco386/Ludolph/downloads>`_ uncompress and 
install with command: python setup.py.install
Make sure all dependencies (listed below) are installed. You also
need to create a config file, you can rename and amend  example file. 
Debian: /usr/local/lib/python2.7/dist-packages/ludolph
Fedora: /usr/lib/python2.7/site-packages/ludolph
There is also a init script installed in /etc/init.d for service
command, unfortunatelly it is for DEBIAN based systems only.
Admin can run the bot by calling command ludolph, script is in
Debian: /usr/local/bin/
Fedora: /usr/bin

**Dependencies:**
sleekxmpp

License
-------

For more informations see LICENSE file
