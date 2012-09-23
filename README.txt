Ludolph
=======

Zabbix monitoring Jabber bot

Installation Notes
------------------

Installation have to be done as root. Download the latest release 
from https://github.com/ricco386/Ludolph/downloads uncompress and 
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

Dependencies:
jabberbot (packaged as python-jabberbot in Debian and Fedora)
xmpppy (packaged as python-xmpp in Debian and Fedora)

Licence
-------

Ludolph - Zabbix monitoring Jabber bot
Copyright (C) 2012 Richard Kellner & Daniel Kontsek

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
