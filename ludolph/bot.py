"""
Ludolph: Monitoring Jabber Bot
Copyright (C) 2012-2013 Erigones s. r. o.
This file is part of Ludolph.

See the LICENSE file for copying permission.
"""

import os
import ssl
import time
import logging
from sleekxmpp import ClientXMPP
from sleekxmpp.xmlstream import ET

from ludolph.message import LudolphMessage
from ludolph.command import COMMANDS, USERS, ADMINS

logger = logging.getLogger(__name__)

__all__ = ['LudolphBot']


class LudolphBot(ClientXMPP):
    """
    Ludolph bot.
    """
    _start_time = None
    _commands = None  # Cached sorted list of commands
    _muc_ready = False
    commands = COMMANDS
    plugins = None
    users = USERS
    admins = ADMINS
    room = None
    room_config = None
    room_users = set()
    room_admins = set()
    muc = None
    nick = 'Ludolph'
    pipe_file = None
    xmpp = None
    maxhistory = '1024'

    def __init__(self, config, plugins=None, *args, **kwargs):
        self._load_config(config)
        logger.info('Initializing *%s* jabber bot', self.nick)
        self._load_plugins(config, plugins)

        # Initialize the SleekXMPP client
        ClientXMPP.__init__(self, config.get('xmpp', 'username'), config.get('xmpp', 'password'))

        # Auto-authorize is enabled by default. User subscriptions are
        # controlled by self._handle_new_subscription
        self.auto_authorize = True

        # Register XMPP plugins
        self.register_plugin('xep_0030')  # Service Discovery
        self.register_plugin('xep_0045')  # Multi-User Chat
        self.register_plugin('xep_0199')  # XMPP Ping

        # Register event handlers
        self.add_event_handler('session_start', self.session_start, threaded=True)
        self.add_event_handler('message', self.message, threaded=True)

        if self.room:
            self.muc = self.plugin['xep_0045']
            self.add_event_handler('groupchat_message', self.muc_message, threaded=True)
            self.add_event_handler('muc::%s::got_online' % self.room, self.muc_online, threaded=True)

        # Start the monitoring thread for reading the pipe file
        self._start_thread('mon_thread', self.mon_thread)

        # Save start time
        self._start_time = time.time()

    def _load_config(self, config):
        """
        Load bot settings from config object.
        """
        logger.info('Configuring jabber bot')

        # Global stuff
        self.pipe_file = config.get('global', 'pipe_file')

        # Get nick name
        if config.has_option('xmpp', 'nick'):
            nick = config.get('xmpp', 'nick').strip()
            if nick:
                self.nick = nick

        # If you are working with an OpenFire server, you will
        # need to use a different SSL version:
        if config.has_option('xmpp', 'sslv3') and config.getboolean('xmpp', 'sslv3'):
            self.ssl_version = ssl.PROTOCOL_SSLv3

        # Read comma-separated option and return a list of JIDs
        def read_jid_array(section, option, keywords=()):
            jids = set()

            if config.has_option(section, option):
                for jid in config.get(section, option).strip().split(','):
                    jid = jid.strip()

                    if not jid:
                        continue

                    if '@' in jid:
                        if jid.startswith('@'):
                            kwd = jid[1:]
                            if kwd in keywords:
                                jids.update(getattr(self, kwd))
                            else:
                                logger.warn('Skipping invalid keyword "%s" from setting "%s"', jid, option)
                        else:
                            jids.add(jid)
                    else:
                        logger.warn('Skipping invalid JID "%s" from setting "%s"', jid, option)

            return jids

        # Users
        self.users.clear()
        self.users.update(read_jid_array('xmpp', 'users'))
        logger.info('Current users: %s', ', '.join(self.users))

        # Admins
        self.admins.clear()
        self.admins.update(read_jid_array('xmpp', 'admins', keywords=('users',)))
        logger.info('Current admins: %s', ', '.join(self.admins))

        # Admins vs. users
        if not self.admins.issubset(self.users):
            for i in self.admins.difference(self.users):
                logger.error('Admin "%s" is not specified in users. '
                             'This may lead to unexpected behaviour. ', i)

        # MUC room
        if config.has_option('xmpp', 'room'):
            self.room = config.get('xmpp', 'room').strip()

        # MUC room users
        self.room_users.clear()
        if self.room:
            self.room_users.update(read_jid_array('xmpp', 'room_users', keywords=('users', 'admins')))
            logger.info('Current room users: %s', ', '.join(self.room_users))

        # MUC room admins
        self.room_admins.clear()
        if self.room:
            self.room_admins.update(read_jid_array('xmpp', 'room_admins', keywords=('users', 'admins', 'room_users')))
            logger.info('Current room admins: %s', ', '.join(self.room_admins))

        # Room admins vs. users
        if not self.room_admins.issubset(self.room_users):
            for i in self.room_admins.difference(self.room_users):
                logger.error('Room admin "%s" is not specified in room_users. '
                             'This may lead to unexpected behaviour. ', i)

    def _load_plugins(self, config, plugins, init=True):
        """
        Initialize plugins.
        The init parameter indicates whether this is a first-time initialization or a reload.
        """
        if init:
            # First-time plugin initialization -> include ourself to plugins dict
            self.xmpp = self
            self.plugins = {__name__: self}
        else:
            # Bot reload - remove disabled plugins
            for enabled_plugin in self.plugins.keys():
                if enabled_plugin == __name__:
                    continue  # Skip ourself

                if not plugins or enabled_plugin not in plugins:
                    logger.info('Disabling plugin %s', enabled_plugin)
                    del self.plugins[enabled_plugin]

        if plugins:
            for plugin, cls in plugins.items():
                if init or plugin not in self.plugins:
                    logger.info('Initializing plugin %s', plugin)
                    self.plugins[plugin] = cls(config, reinit=False)
                else:
                    logger.info('Reloading plugin %s', plugin)
                    del self.plugins[plugin]
                    self.plugins[plugin] = cls(config, reinit=True)
                # xmpp attribute pointing to this instance is available in plugin object
                setattr(self.plugins[plugin], 'xmpp', self)

        cmds = self.available_commands(reset=True)
        logger.info('Registered commands: %s', ', '.join(cmds))

    def _room_members(self):
        """
        Change multi-user chat room member list.
        """
        query = ET.Element('{http://jabber.org/protocol/muc#admin}query')
        qitem = '{http://jabber.org/protocol/muc#admin}item'
        query.append(ET.Element(qitem, {'affiliation': 'owner', 'jid': self.boundjid.bare}))

        for jid in self.room_users:
            if jid in self.room_admins:
                affiliation = 'admin'
            else:
                affiliation = 'member'

            item = ET.Element(qitem, {'affiliation': affiliation, 'jid': jid})
            query.append(item)

        iq = self.make_iq_set(query)
        iq['to'] = self.room
        iq['from'] = ''
        iq.send()

    def _room_config(self):
        """
        Configure multi-user chat room.
        """
        logger.info('Getting current configuration for MUC room %s', self.room)

        try:
            self.room_config = self.muc.getRoomConfig(self.room)
        except ValueError:
            logger.error('Could not get MUC room configuration. Maybe the room is not (properly) initialized.')
            return

        if self.room_users:
            self.room_config['fields']['muc#roomconfig_membersonly']['value'] = True
            self.room_config['fields']['members_by_default']['value'] = False
        else:
            self.room_config['fields']['muc#roomconfig_membersonly']['value'] = False
            self.room_config['fields']['members_by_default']['value'] = True

        logger.info('Setting new configuration for MUC room %s', self.room)
        self.muc.setRoomConfig(self.room, self.room_config)
        logger.info('Setting member list for MUC room %s', self.room)
        self._room_members()

    def _jid_in_room(self, jid):
        """
        Determine if jid is present in chat room.
        """
        for nick in self.muc.rooms[self.room]:
            entry = self.muc.rooms[self.room][nick]

            if entry is not None and entry['jid'].bare == jid:
                return True

        return False

    def _handle_new_subscription(self, pres):
        """
        xmpp.auto_authorize is True by default, which is fine. But we want to
        restrict this to users only (if set). We do this by overriding the
        automatic subscription mechanism.
        """
        user = pres['from']

        if not self.users or user in self.users:
            logger.info('Allowing user "%s" to auto subscribe', user)
            return super(LudolphBot, self)._handle_new_subscription(pres)
        else:
            logger.warning('User "%s" is not allowed to subscribe', user)

    def get_jid(self, msg, bare=True):
        """
        Helper method for retrieving jid from message.
        """
        if msg['type'] == 'groupchat' and self.room:
            jid = self.muc.getJidProperty(msg['mucroom'], msg['mucnick'], 'jid')
        else:
            jid = msg['from']

        if bare and jid:
            return jid.bare

        return jid

    def session_start(self, event):
        """
        Process the session_start event.
        """
        self.get_roster()
        self.roster_cleanup()
        self.send_presence(pnick=self.nick)

        if self.room and self.muc:
            logger.info('Initializing multi-user chat room %s', self.room)
            self.muc.joinMUC(self.room, self.nick, maxhistory=self.maxhistory)

    def roster_cleanup(self):
        """
        Remove roster items with none subscription.
        """
        roster = self.client_roster
        logger.info('Current roster: %s', ', '.join(roster.keys()))

        # Remove users with none subscription from roster
        # Also remove users that are not in users setting (if set)
        for i in roster.keys():
            if roster[i]['subscription'] == 'none' or (self.users and i not in self.users):
                logger.warning('Roster item: %s (%s) - removing!', i, roster[i]['subscription'])
                self.send_presence(pto=i, ptype='unsubscribe')
                self.del_roster_item(i)
            else:
                logger.info('Roster item: %s (%s) - ok', i, roster[i]['subscription'])

    def muc_online(self, presence):
        """
        Process a presence stanza from a chat room.
        """
        # Configure room and say hello from jabber bot if this is a presence stanza
        if presence['from'] == '%s/%s' % (self.room, self.nick):
            self._room_config()
            self.msg_send(self.room, '%s is here!' % self.nick, mtype='groupchat')
            self._muc_ready = True
            self.send_presence(pto=presence['from'])
            logger.info('People in MUC room: %s', ', '.join(self.muc.getRoster(self.room)))

            # Send invitation to all users
            for user in self.room_users:
                if self._jid_in_room(user):
                    logger.info('User "%s" already in MUC room', user)
                elif user != self.room:
                    logger.info('Inviting "%s" to MUC room', user)
                    self.muc.invite(self.room, user)

        else:
            # Say hello to new user
            muc = presence['muc']
            logger.info('User "%s" with nick "%s", role "%s" and affiliation "%s" is joining MUC room',
                        muc['jid'], muc['nick'], muc['role'], muc['affiliation'])
            self.msg_send(presence['from'].bare, 'Hello %s!' % muc['nick'], mtype='groupchat')

    def available_commands(self, reset=False):
        """
        List of all available bot commands.
        """
        # Remove commands from disabled plugins
        if reset:
            for cmd_name, cmd in self.commands.items():
                if cmd['module'] not in self.plugins:
                    del self.commands[cmd_name]
            self._commands = None

        # Sort and cache
        if self._commands is None:
            self._commands = sorted(self.commands.keys())

        return self._commands

    def get_command(self, cmdstr):
        """
        Find text in available commands and return command dict.
        """
        if not cmdstr:
            return None

        if cmdstr in self.available_commands():
            cmd = self.commands[cmdstr]
        else:
            for key in self.available_commands():
                if key.startswith(cmdstr):
                    cmd = self.commands[key]
                    cmdstr = key
                    break
            else:
                return None

        cmd['str'] = cmdstr

        return cmd

    def message(self, msg, types=('chat', 'normal')):
        """
        Incoming message handler.
        """
        if msg['type'] not in types:
            return

        # Seek received text in available commands and get command
        cmd = self.get_command(msg['body'].split()[0].strip())

        if cmd:
            start_time = time.time()
            f_cmd = getattr(self.plugins[cmd['module']], cmd['name'])
            # Run command
            out = f_cmd(msg)

            if out:
                cmd_time = time.time() - start_time
                logger.info('Command %s.%s finished in %g seconds', cmd['module'], cmd['name'], cmd_time)

            return out
        else:
            # Send message that command was not understood and what to do
            return msg.reply('Sorry, I don\'t understand "%s"\n'
                             'Please type "help" for more info' % msg['body']).send()

    def muc_message(self, msg):
        """
        MUC Incoming message handler.
        """
        if not self._muc_ready:
            return

        if msg['mucnick'] == self.nick:
            return

        # Respond to the message only if the bots nickname is mentioned
        # And only if we can get user's JID
        nick = self.nick + ':'
        if msg['body'].startswith(nick) and self.get_jid(msg):
            msg['body'] = msg['body'].lstrip(nick).lstrip()
            return self.message(msg, types=('groupchat',))

    def shutdown(self, signalnum, handler):
        """
        Shutdown signal handler.
        """
        logger.info('Requested shutdown (%s)', signalnum)

        return self.abort()

    def reload(self, config, plugins=None):
        """
        Reload bot configuration and plugins.
        """
        logger.info('Requested reload')
        self._load_config(config)
        self._load_plugins(config, plugins, init=False)

        if self.room and self.muc:
            self._muc_ready = False
            self.muc.leaveMUC(self.room, self.nick)
            logger.info('Reinitializing multi-user chat room %s', self.room)
            self.muc.joinMUC(self.room, self.nick, maxhistory=self.maxhistory)

    def mon_thread(self):
        """
        Processing input from the monitoring pipe file.
        """
        with os.fdopen(os.open(self.pipe_file, os.O_RDONLY | os.O_NONBLOCK)) as fifo:
            logger.info('Processing input from monitoring pipe file')
            while not self.stop.is_set():
                line = fifo.readline().strip()
                if line:
                    data = line.split(';', 1)
                    if len(data) == 2:
                        logger.info('Sending monitoring message to "%s"', data[0])
                        logger.debug('\twith body: "%s"', data[1])

                        if data[0] == self.room:
                            mtype = 'groupchat'
                        else:
                            mtype = 'normal'

                        self.msg_send(data[0], data[1], mtype=mtype)

                    else:
                        logger.warning('Bad message format ("%s")', line)

                time.sleep(1)

                if self.stop.is_set():
                    self._end_thread('mon_thread', early=True)
                    return

    def msg_send(self, mto, mbody, **kwargs):
        """
        Create message and send it.
        """
        return LudolphMessage.create(mbody, **kwargs).send(self, mto)

    def msg_reply(self, msg, mbody, **kwargs):
        """
        Set message reply text and html, and send it.
        """
        if mbody is None:
            return None  # Command performs custom message sending

        return LudolphMessage.create(mbody, **kwargs).reply(msg)
