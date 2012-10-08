#!/usr/bin/python

from version import VERSION

def version():
    return 'Version: '+ VERSION

def about():
    return """
    Ludolph - Zabbix monitoring Jabber bot
    Version: """+ VERSION +"""
    Homepage: https://github.com/ricco386/Ludolph
    Copyright (C) 2012 Richard Kellner & Daniel Kontsek
    This program comes with ABSOLUTELY NO WARRANTY. For details type `about
    licence'.
    This is free software, and you are welcome to redistribute it under
    certain conditions."""

def licence():
    return """
    Ludolph - Zabbix monitoring Jabber bot \
    Copyright (C) 2012 Richard Kellner & Daniel Kontsek

    This program is free software: you can redistribute it and/or modify it
    under the terms of the GNU General Public License as published by the Free
    Software Foundation, either version 3 of the License.

    This program is distributed in the hope that it will useful, but WITHOUT
    ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
    FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
    more details.

    You should have received a copy of the GNU General Public License along
    with this program. If not, see <http://www.gnu.org/licenses/>.
    """
