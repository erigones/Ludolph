"""
Ludolph: Monitoring Jabber bot
Copyright (C) 2012-13 Erigones s.r.o.
This file is part of Ludolph.

See the file LICENSE for copying permission.
"""

from zabbixAPI.zabbix_api import ZabbixAPI

class zabbixConnect():

    def __init__(self, config):
        self.config = config
        zapi = ZabbixAPI(server = config.get('zabbix','server'),
                path="",
                log_level=30)
        zapi.login(config.get('zabbix','username'),
                config.get('zabbix','password'))
        self.zapi = zapi

    def testLogin(self):
        return str(self.zapi.test_login())

    def getZabbixApiVersion(self):
        return self.zapi.api_version()
