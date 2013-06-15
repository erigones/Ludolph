"""
Ludolph: Monitoring Jabber bot
Copyright (C) 2012-13 Erigones s.r.o.
This file is part of Ludolph.

See the file LICENSE for copying permission.
"""
import logging
from tabulate import tabulate

from ludolph.command import command, parameter_required, admin_required
from ludolph.plugins.plugin import LudolphPlugin
from ludolph.plugins.zabbix_api import ZabbixAPI, ZabbixAPIException

TIMEOUT = 10
TABLEFMT = 'simple'

logger = logging.getLogger(__name__)

def zabbix_command(f):
    """
    Decorator for executing zabbix API commands and doing a relogin if needed.
    """
    def wrap(obj, msg, *args, **kwargs):
        errmsg = 'Zabbix API not available'

        # Was never logged in. Repair authentication and restart Ludolph.
        if not obj.zapi.logged_in():
            logger.error(errmsg)
            msg.reply(errmsg).send()
            return None

        try:
            return f(obj, msg, *args, **kwargs)
        except ZabbixAPIException as ex:
            logger.error('Zabbix API error (%s)', ex)

            # Try to relogin
            try:
                logger.info('Zabbix API relogin')
                obj.zapi.auth = '' # Reset auth before relogin
                obj.zapi.login()
            except ZabbixAPIException as e:
                # Relogin failed. Repair authentication and restart Ludolph.
                logger.critical('Zabbix API login error (%s)', e)
                obj.zapi.auth = '' # logged_in() will always return False
                msg.reply(errmsg).send()
                return None
            else:
                # Relogin successfull, Try to run command
                try:
                    return f(obj, msg, *args, **kwargs)
                except ZabbixAPIException as exc:
                    err = 'Zabbix API error (%s)' % exc
                    logger.error(err)
                    msg.reply(err).send()

    return wrap

class Zabbix(LudolphPlugin):
    """
    Zabbix API connector for LudolphBot.
    """
    zapi = None

    def __init__(self, config, *args, **kwargs):
        """
        Initialize zapi and try to login.
        """
        # HTTP authentication?
        httpuser = None
        httppasswd = None
        if config.has_option('zabbix', 'httpuser'):
            httpuser = config.get('zabbix', 'httpuser')
        if config.has_option('zabbix', 'httppasswd'):
            httppasswd = config.get('zabbix', 'httppasswd')

        self.zapi = ZabbixAPI(server=config.get('zabbix','server'),
                user=httpuser, passwd=httppasswd, timeout=TIMEOUT,
                log_level=logging.getLevelName(config.get('global','loglevel')))

        # Login and save zabbix credentials
        try:
            logger.info('Zabbix API login')
            self.zapi.login(config.get('zabbix', 'username'),
                            config.get('zabbix', 'password'), save=True)
        except ZabbixAPIException as e:
            logger.critical('Zabbix API login error (%s)', e)

    @zabbix_command
    @command
    def zabbix_version(self, msg):
        """
        Show version of Zabbix API.
        """
        return 'Zabbix API version: '+ self.zapi.api_version()

    @zabbix_command
    @command
    def alerts(self, msg):
        """
        List current zabbix alerts.

        Emulates include/blocks.inc.php :: make_latest_issues()
        """
        # get triggers
        options = {
                'groupids': None,
                'hostids': None,
                'monitored': True,
                'maintenance': False,
                'skipDependent': True,
                'filter': {'priority': None, 'value': 1}, # TRIGGER_VALUE_TRUE
                'selectHosts': ['hostid', 'name'],
                'output': ['triggerid', 'value_flags', 'error', 'url', 'expression', 'description', 'priority', 'type'],
                'sortfield': 'lastchange',
                'sortorder': 'DESC', # ZBX_SORT_DOWN
        }
        triggers = self.zapi.trigger.get(options)

        for tnum, trigger in enumerate(triggers):
            # if trigger is lost (broken expression) we skip it
            if not trigger['hosts']:
                del triggers[tnum]
                continue

            host = trigger['hosts'][0]
            trigger['hostid'] = host['hostid']
            trigger['hostname'] = host['name']

            triggers[tnum] = trigger

        # get hosts
        hosts = self.zapi.host.get({
            'hostids': [int(i['hostid']) for i in triggers],
            'output': ['hostid', 'name', 'maintenance_status', 'maintenance_type', 'maintenanceid'],
            'selectInventory': ['hostid'],
            'selectScreens': 'count', #API_OUTPUT_COUNT
            'preservekeys': True,
        })

        # output
        table = []
        for trigger in triggers:
            # get last event
            events = self.zapi.event.get({
                    'output': 'extend',
                    'select_acknowledges': 'extend',
                    'triggerids': trigger['triggerid'],
                    'filter': {
                            'object': 0, # EVENT_OBJECT_TRIGGER
                            'value': 1, # TRIGGER_VALUE_TRUE
                            'value_changed': 1, # TRIGGER_VALUE_CHANGED_YES
                    },
                    'sortfield': ['object', 'objectid', 'eventid'],
                    'sortorder': 'DESC',
                    'limit': 1,
            })

            # Event
            if not events:
                continue # WTF?
            event = events[0]
            eventid = event['eventid']

            # Host and hostname
            host = hosts[trigger['hostid']]
            hostname = host['name']
            if int(host['maintenance_status']):
                hostname += '*' # some kind of maintenance TODO

            # Trigger description
            desc = str(trigger['description'])
            if trigger['error'] or int(trigger['value_flags']):
                desc += '*' # some kind of trigger error TODO

            # Priority
            prio = self.zapi.get_severity(trigger['priority'])

            # Last change and age
            dt = self.zapi.get_datetime(trigger['lastchange'])
            #last = self.zapi.convert_datetime(dt)
            age = self.zapi.get_age(dt)

            # Ack
            if int(event['acknowledged']):
                ack = 'Yes'
            else:
                ack = 'No'

            table.append([eventid, hostname, desc, prio, age, ack])

        out = str(tabulate(table, headers=['EventID', 'Host', 'Issue',
            'Severity', 'Age', 'Ack'], tablefmt=TABLEFMT))
        out += '\n\n%d issues are shown.\n%s' % (
            len(triggers), self.zapi.server + '/aaa.php')

        return out

    @zabbix_command
    @parameter_required(1)
    @command
    def ack(self, msg, eventid):
        """
        Acknowledge event. EventID is a required parameter.
        """
        ret = self.zapi.event.acknowledge({
            'eventids': [eventid],
            'message': str(msg['from']),
        })
        return 'Event %s acknowledged' % eventid
