"""
Ludolph: Monitoring Jabber bot
Copyright (C) 2012-2014 Erigones s. r. o.
This file is part of Ludolph.

See the file LICENSE for copying permission.
"""
import logging
from datetime import datetime, timedelta

from ludolph.utils import parse_loglevel
from ludolph.web import webhook, request, abort
from ludolph.cron import cronjob
from ludolph.command import command, parameter_required
from ludolph.message import red, green
from ludolph.plugins.plugin import LudolphPlugin
from ludolph.plugins.zabbix_api import ZabbixAPI, ZabbixAPIException

logger = logging.getLogger(__name__)

TIMEOUT = 10
DUTY_GROUP = 'On-Call Duty'


def zabbix_command(fun):
    """
    Decorator for executing zabbix API commands and checking zabbix API errors.
    """
    def wrap(obj, msg, *args, **kwargs):
        def api_error(errmsg='Zabbix API not available'):
            # Log and reply with error message
            logger.error(errmsg)
            obj.xmpp.msg_reply(msg, 'ERROR: ' + errmsg)
            return None

        # Was never logged in. Repair authentication and restart Ludolph.
        if not obj.zapi.logged_in():
            return api_error()

        try:
            return fun(obj, msg, *args, **kwargs)
        except ZabbixAPIException as ex:
            # API command problem
            return api_error('Zabbix API error (%s)' % ex)

    return wrap


class Zabbix(LudolphPlugin):
    """
    Zabbix API connector for LudolphBot.

    Zabbix >= 2.0.6 is required.
    https://www.zabbix.com/documentation/2.0/manual/appendix/api/api
    """
    zapi = None

    # noinspection PyMissingConstructor,PyUnusedLocal
    def __init__(self, xmpp, config, **kwargs):
        """
        Login to zabbix.
        """
        self.xmpp = xmpp
        self.init(dict(config))

    def init(self, config):
        """
        Initialize zapi and try to login.
        """
        # HTTP authentication?
        httpuser = config.get('httpuser', None)
        httppasswd = config.get('httppasswd', None)

        self.zapi = ZabbixAPI(server=config['server'], user=httpuser, passwd=httppasswd, timeout=TIMEOUT,
                              log_level=parse_loglevel(config.get('loglevel', 'INFO')))

        # Login and save zabbix credentials
        try:
            logger.info('Zabbix API login')
            self.zapi.login(config['username'], config['password'], save=True)
        except ZabbixAPIException as e:
            logger.critical('Zabbix API login error (%s)', e)

    @webhook('/alert', methods=('POST',))
    def alert(self):
        """
        Process zabbix alert request and send xmpp message to user/room.
        """
        jid = request.forms.get('jid', None)

        if not jid:
            logger.warning('Missing JID in alert request')
            abort(400, 'Missing JID in alert request')

        if jid == self.xmpp.room:
            mtype = 'groupchat'
        else:
            mtype = 'normal'

        msg = request.forms.get('msg', '')
        logger.info('Sending monitoring alert to "%s"', jid)
        logger.debug('\twith body: "%s"', msg)
        self.xmpp.msg_send(jid, msg, mtype=mtype)

        return 'Message sent'

    # noinspection PyUnusedLocal
    @zabbix_command
    @command
    def zabbix_version(self, msg):
        """
        Show version of Zabbix API.

        Usage: zabbix-version
        """
        return 'Zabbix API version: ' + self.zapi.api_version()

    # noinspection PyUnusedLocal
    @zabbix_command
    @command
    def alerts(self, msg):
        """
        Show a list of current zabbix alerts with notes attach to each event ID.

        Usage: alerts
        """
        notes = True
        out = []
        # Get triggers
        triggers = self.zapi.trigger.get({
            'groupids': None,
            'hostids': None,
            'monitored': True,
            'maintenance': False,
            'skipDependent': True,
            'filter': {'priority': None, 'value': 1},  # TRIGGER_VALUE_TRUE
            'selectHosts': ['hostid', 'name', 'maintenance_status', 'maintenance_type', 'maintenanceid'],
            'selectLastEvent':  'extend',  # API_OUTPUT_EXTEND
            'output': ['triggerid', 'value_flags', 'error', 'url', 'expression',
                       'description', 'priority', 'type', 'comments'],
            'sortfield': 'lastchange',
            'sortorder': 'DESC',  # ZBX_SORT_DOWN
        })

        # Get notes = event acknowledges
        if notes:
            events = self.zapi.event.get({
                'eventids': [t['lastEvent']['eventid'] for t in triggers if t['lastEvent']],
                'output': 'extend',
                'select_acknowledges': 'extend',
                'sortfield': 'eventid',
                'sortorder': 'DESC',
            })

        for trigger in triggers:
            # If trigger is lost (broken expression) we skip it
            if not trigger['hosts']:
                continue

            # Event
            event = trigger['lastEvent']
            if event:
                eventid = event['eventid']
                # Ack
                if int(event['acknowledged']):
                    ack = '^^**ACK**^^'
                else:
                    ack = ''
            else:
                # WTF?
                eventid = '????'
                ack = ''

            # Host and hostname
            host = trigger['hosts'][0]
            hostname = host['name']
            if int(host['maintenance_status']):
                hostname += ' **++**'  # some kind of maintenance

            # Trigger description
            desc = str(trigger['description'])
            if trigger['error'] or int(trigger['value_flags']):
                desc += ' **??**'  # some kind of trigger error

            # Priority
            prio = self.zapi.get_severity(trigger['priority']).ljust(12)

            # Last change and age
            dt = self.zapi.get_datetime(trigger['lastchange'])
            #last = self.zapi.convert_datetime(dt)
            age = '^^%s^^' % self.zapi.get_age(dt)

            comments = ''
            if trigger['error']:
                comments += '\n\t\t^^**Error:** %s^^' % trigger['error']

            if trigger['comments']:
                comments += '\n\t\t^^%s^^' % trigger['comments'].strip()

            acknowledges = ''
            if notes:
                for i, e in enumerate(events):
                    if e['eventid'] == event['eventid']:
                        for a in e['acknowledges']:
                            acknowledges = '\n\t\t__%s: %s__' % (self.zapi.get_datetime(a['clock']),
                                                                 a['message']) + acknowledges
                        del events[i]
                        break

            out.append('**%s**\t%s\t%s\t%s\t%s\t%s%s%s\n' % (eventid, prio, hostname, desc, age,
                                                             ack, comments, acknowledges))

        out.append('\n**%d** issues are shown.\n%s/tr_status.php?groupid=0&hostid=0' % (len(triggers),
                                                                                        self.zapi.server))

        return '\n'.join(out)

    @zabbix_command
    @parameter_required(1)
    @command
    def ack(self, msg, eventid, *eventids_or_note):
        """
        Acknowledge event(s) with optional note.

        Usage: ack <event ID> [event ID2] [event ID3] ... [note]
        """
        try:
            eventids = [int(eventid)]
        except ValueError:
            return 'ERROR: Integer required'

        note = 'ack'

        for i, arg in enumerate(eventids_or_note):
            try:
                eid = int(arg)
            except ValueError:
                note = ' '.join(eventids_or_note[i:])
                break
            else:
                eventids.append(eid)

        message = '%s: %s' % (self.xmpp.get_jid(msg), note)

        res = self.zapi.event.acknowledge({
            'eventids': eventids,
            'message': message,
        })

        return 'Event ID(s) **%s** acknowledged' % ','.join(map(str, res.get('eventids', ())))

    # noinspection PyUnusedLocal
    def _outage_del(self, msg, mid):
        """
        Delete maintenance period specified by maintenance ID.

        Usage: outage-del <maintenance ID>
        """
        try:
            mid = int(mid)
        except ValueError:
            return 'ERROR: Integer required'

        self.zapi.maintenance.delete([mid])

        return 'Maintenance ID **%s** deleted' % mid

    def _outage_add(self, msg, host_or_group, duration):
        """
        Set maintenance period for specified host and time.

        Usage: outage-add <host/group name> <duration in minutes>
        """
        # Get start and end time
        try:
            duration = int(duration)
        except ValueError:
            return 'ERROR: Integer required'

        period = timedelta(minutes=duration)
        _now = datetime.now()
        _end = _now + period
        now = _now.strftime('%s')
        end = _end.strftime('%s')
        jid = self.xmpp.get_jid(msg)
        options = {
            'active_since': now,
            'active_till': end,
            'maintenance_type': 0,  # with data collection
            'timeperiods': [{
                'timeperiod_type': 0,  # one time only
                'start_date': now,
                'period': period.seconds,
            }],
        }

        # Get hosts
        hosts = self.zapi.host.get({
            'search': {'name': host_or_group},
            'output': ['hostid', 'name'],
        })

        if hosts:
            options['hostids'] = [i['hostid'] for i in hosts]
            desc = 'hosts: ' + ', '.join([i['name'] for i in hosts])
        else:
            # Get groups
            groups = self.zapi.hostgroup.get({
                'search': {'name': host_or_group},
                'output': ['groupids', 'name'],
            })

            if groups:
                options['groupids'] = [i['groupid'] for i in groups]
                desc = 'groups: ' + ', '.join([i['name'] for i in groups])
            else:
                return "ERROR: Host/Group not found"

        options['name'] = ('Maintenance %s by %s' % (now, jid))[:128]
        options['description'] = desc

        # Create maintenance period
        res = self.zapi.maintenance.create(options)

        return 'Added maintenance ID **%s** for %s' % (res['maintenanceids'][0], desc)

    @zabbix_command
    @command
    def outage(self, msg, mid_or_host_or_group=None, duration=None):
        """
        Show, create or delete maintenance periods.

        Show all maintenance periods.
        Usage: outage

        Set maintenance period for specified host and time.
        Usage: outage <host/group name> <duration in minutes>

        Delete maintenance period specified by maintenance ID.
        Usage: outage <maintenance ID>
        """
        if duration:
            return self._outage_add(msg, mid_or_host_or_group, duration)
        elif mid_or_host_or_group:
            return self._outage_del(msg, mid_or_host_or_group)

        out = []
        # Display list of maintenances
        maintenances = self.zapi.maintenance.get({
            'output': 'extend',
            'sortfield': ['maintenanceid', 'name'],
            'sortorder': 'ASC',
        })

        for i in maintenances:
            if i['description']:
                desc = '\n\t^^%s^^' % i['description']
            else:
                desc = ''

            since = self.zapi.timestamp_to_datetime(i['active_since'])
            until = self.zapi.timestamp_to_datetime(i['active_till'])
            out.append('**%s**\t%s - %s\t__%s__%s\n' % (i['maintenanceid'], since, until, i['name'], desc))

        out.append('\n**%d** maintenances are shown.\n%s' % (len(maintenances),
                                                             self.zapi.server + '/maintenance.php?groupid=0'))

        return '\n'.join(out)

    @cronjob(minute=range(0, 60, 5))
    def maintenance(self):
        """
        Cron job for cleaning outdated outages and informing about incoming outage end.
        """
        maintenances = self.zapi.maintenance.get({
            'output': 'extend',
            'sortfield': ['maintenanceid', 'name'],
            'sortorder': 'ASC',
        })
        now = datetime.now()
        in5 = now + timedelta(minutes=5)

        for i in maintenances:
            until = self.zapi.get_datetime(i['active_till'])
            mid = i['maintenanceid']
            name = i['name']
            desc = i['description'] or ''

            if until < now:
                logger.info('Deleting maintenance %s (%s)', mid, name)
                self.zapi.maintenance.delete([mid])
                msg = 'Maintenance ID **%s** ^^(%s)^^ deleted' % (mid, desc)
            elif until < in5:
                logger.info('Sending notification about maintenance %s (%s) end', mid, name)
                msg = 'Maintenance ID **%s** ^^(%s)^^ is going to end %s' % (mid, desc,
                                                                             until.strftime('on %Y-%m-%d at %H:%M:%S'))
            else:
                continue

            jid = name.split()[-1]

            if '@' in jid:
                self.xmpp.msg_send(jid.strip(), msg)
            else:
                logging.warning('Missing JID in maintenance %s (%s)"', mid, name)

    # noinspection PyUnusedLocal
    @zabbix_command
    @command
    def hosts(self, msg, hoststr=None):
        """
        Show a list of hosts.

        Usage: hosts [host name search string]
        """
        out = []
        params = {
            'output': ['hostid', 'name', 'available', 'maintenance_status', 'status'],
            'selectInventory': 1,  # All inventory items
            'sortfield': ['name', 'hostid'],
            'sortorder': 'ASC',
        }

        if hoststr:
            params['search'] = {'name': hoststr}

        # Get hosts
        hosts = self.zapi.host.get(params)

        for host in hosts:
            if int(host['maintenance_status']):
                host['name'] += ' **++**'  # some kind of maintenance

            if int(host['status']):
                status = 'Not monitored'
            else:
                status = 'Monitored'

            ae = int(host['available'])
            available = 'Z'
            if ae == 1:
                available = green('Z')
            elif ae == 2:
                available = red('Z')

            _inventory = []
            if host['inventory']:
                for key, val in host['inventory'].items():
                    if val and key not in ('inventory_mode', 'hostid'):
                        _inventory.append('**%s**: %s' % (key, val))

            if _inventory:
                inventory = '\n\t\t^^%s^^' % str(', '.join(_inventory)).strip()
            else:
                inventory = ''

            out.append('**%s**\t%s\t%s\t%s%s' % (host['hostid'], host['name'], status, available, inventory))

        out.append('\n**%d** hosts are shown.\n%s/hosts.php?groupid=0' % (len(hosts), self.zapi.server))

        return '\n'.join(out)

    # noinspection PyUnusedLocal
    @zabbix_command
    @command
    def groups(self, msg, groupstr=None):
        """
        Show a list of host groups.

        Usage: groups [group name search string]
        """
        out = []
        params = {
            'output': ['groupid', 'name'],
            'selectHosts': ['hostid', 'name'],
            'sortfield': ['name', 'groupid'],
            'sortorder': 'ASC',
        }

        if groupstr:
            params['search'] = {'name': groupstr}

        # Get groups
        groups = self.zapi.hostgroup.get(params)

        for group in groups:
            _hosts = ['**%s**: %s' % (h['hostid'], h['name']) for h in group['hosts'] if h]
            hosts = '\n\t\t^^%s ^^' % ', '.join(_hosts)
            out.append('**%s**\t%s%s' % (group['groupid'], group['name'], hosts))

        out.append('\n**%d** hostgroups are shown.\n%s/hostgroups.php' % (len(groups), self.zapi.server))

        return '\n'.join(out)

    # noinspection PyUnusedLocal
    @zabbix_command
    @command
    def duty(self, msg):
        """
        Show a list of users in duty user group.

        Usage: duty
        """
        # Get group
        duty = self.zapi.usergroup.get({
            'filter': {'name': DUTY_GROUP},
            'output': ['usrgrpid', 'name', 'users_status'],
            'selectUsers': 'extend',  # API_OUTPUT_EXTEND
        })
        out = []

        if not len(duty):
            return 'ERROR: Duty user group ("%s") not found' % DUTY_GROUP

        for u in duty[0]['users']:
            if int(u['users_status']):
                status = red('disabled')
            else:
                status = green('enabled')

            out.append('%s\t%s' % (u['alias'], status))

        out.append('\n**%d** users in duty group.' % len(duty[0]['users']))

        return '\n'.join(out)