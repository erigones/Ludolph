"""
Ludolph: Monitoring Jabber Bot
Copyright (C) 2012-13 Erigones s. r. o.
This file is part of Ludolph.

See the LICENSE file for copying permission.
"""

import os
import ssl
import time
import logging
from sleekxmpp import ClientXMPP
from tabulate import tabulate

from ludolph.command import COMMANDS, USERS, ADMINS, command, parameter_required, admin_required
from ludolph.__init__ import __doc__ as ABOUT
from ludolph.__init__ import __version__ as VERSION

TABLEFMT = 'simple'

logger = logging.getLogger(__name__)


class LudolphBot(ClientXMPP):
    """
    Ludolph bot.
    """
    _start_time = None
    _commands = None  # Cached sorted list of commands
    commands = COMMANDS
    users = USERS
    admins = ADMINS
    plugins = None
    room = None
    muc = None
    nick = 'Ludolph'

    def __init__(self, config, plugins=None, *args, **kwargs):
        # Get nick name
        if config.has_option('xmpp', 'nick'):
            nick = config.get('xmpp', 'nick').strip()
            if nick:
                self.nick = nick

        logger.info('Initializing *%s* jabber bot', self.nick)

        # Initialize the SleekXMPP client
        ClientXMPP.__init__(self, config.get('xmpp', 'username'), config.get('xmpp', 'password'))

        # If you are working with an OpenFire server, you will
        # need to use a different SSL version:
        if config.has_option('xmpp', 'sslv3') and config.getboolean('xmpp', 'sslv3'):
            self.ssl_version = ssl.PROTOCOL_SSLv3

        # Auto-authorize is enabled by default. User subscriptions are
        # controlled by self._handle_new_subscription
        self.auto_authorize = True

        # Rest of the configuration
        self.config = config
        self.pipe_file = config.get('global', 'pipe_file')

        # Users
        if config.has_option('xmpp', 'users'):
            for i in config.get('xmpp', 'users').strip().split(','):
                i = i.strip()
                if i:
                    self.users.append(i)

        # Admins
        if config.has_option('xmpp', 'admins'):
            for i in config.get('xmpp', 'admins').strip().split(','):
                i = i.strip()
                if i:
                    self.admins.append(i)

        # Admins vs. users
        if self.admins and self.users:
            for i in self.admins:
                if i not in self.users:
                    logger.error('Admin user "%s" is not specified in users. '
                                 'This may lead to unexpected behaviour. ', i)

        # MUC room
        if config.has_option('xmpp', 'room'):
            self.room = config.get('xmpp', 'room').strip()

        # Initialize plugins
        self.plugins = {__name__: self}
        if plugins:
            for plugin, cls in plugins.items():
                logger.info('Initializing plugin %s', plugin)
                self.plugins[plugin] = cls(config)

        # Register XMPP plugins
        self.register_plugin('xep_0030')  # Service Discovery
        self.register_plugin('xep_0045')  # Multi-User Chat
        self.register_plugin('xep_0199')  # XMPP Ping
        self.register_plugin('old_0004')  # Multi-User Chat dependency

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

    def _get_jid(self, msg):
        """
        Helper method for retrieving jid from message.
        """
        if msg['type'] == 'groupchat' and self.room:
            return self.muc.getJidProperty(msg['mucroom'], msg['mucnick'], 'jid')

        return msg['from']

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

    def session_start(self, event):
        """
        Process the session_start event.
        """
        self.get_roster()
        self.roster_cleanup()
        self.send_presence(pnick=self.nick)
        logger.info('Registered commands: %s', ', '.join(self.available_commands()))

        if self.room:
            logger.info('Initializing multi-user chat room %s', self.room)
            self.muc.joinMUC(self.room, self.nick, maxhistory='64', wait=False)

    def roster_cleanup(self):
        """
        Remove roster items with none subscription.
        """
        roster = self.client_roster
        logger.info('Current auto_authorize: %s', self.auto_authorize)
        logger.info('Current users: %s', ', '.join(self.users))
        logger.info('Current admins: %s', ', '.join(self.admins))
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
        # Say hello if this is a presence stanza for jabber bot
        if presence['from'] == '%s/%s' % (self.room, self.nick):
            self.send_message(mto=self.room, mbody='%s is here!' % self.nick, mtype='groupchat')

            # Send invitation to all users in roster
            for user in self.client_roster.keys():
                if self._jid_in_room(user):
                    logger.info('User "%s" already in MUC room %s', user, self.room)
                elif user != self.room:
                    logger.info('Inviting "%s" to MUC room %s', user, self.room)
                    self.muc.invite(self.room, user)

        # Say hello to new user
        if presence['muc']['nick'] != self.nick:
            msg = 'Hello, %s %s' % (presence['muc']['role'], presence['muc']['nick'])
            self.send_message(mto=presence['from'].bare, mbody=msg, mtype='groupchat')

    def available_commands(self):
        """
        List of all available bot commands.
        """
        # Sort and cache
        if self._commands is None:
            self._commands = sorted(self.commands.keys())

        return self._commands

    def message(self, msg, types=('chat', 'normal')):
        """
        Incoming message handler.
        """
        if msg['type'] not in types:
            return

        # Seek received text in available commands
        cmd = msg['body'].split()[0].strip()

        if cmd in self.available_commands():
            # Find and run command
            cmd = self.commands[cmd]
            f = getattr(self.plugins[cmd['module']], cmd['name'])
            return f(msg)
        else:
            # Send message that command was not understood and what to do
            msg.reply('Sorry, I don\'t understand "%s"\n'
                      'Please type "help" for more info' % msg['body']).send()

    def muc_message(self, msg):
        """
        MUC Incoming message handler.
        """
        if msg['mucnick'] == self.nick:
            return

        # Respond to the message only if the bots nickname is mentioned
        nick = self.nick + ':'

        if msg['body'].startswith(nick):
            msg['body'] = msg['body'].lstrip(nick).lstrip()
            return self.message(msg, types=('groupchat',))

    def shutdown(self, signalnum, handler):
        """
        Shutdown signal handler.
        """
        logger.info('Requested shutdown (%s)', signalnum)

        return self.abort()

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

                        self.send_message(mto=data[0], mbody=data[1], mtype=mtype)

                    else:
                        logger.warning('Bad message format ("%s")', line)

                time.sleep(1)

                if self.stop.is_set():
                    self._end_thread('mon_thread', early=True)
                    return

    @command
    def help(self, msg):
        """
        Show this help.

        Usage: help
        """
        cmdline = msg['body'].strip().split()

        # Global help or command help?
        if len(cmdline) > 1 and cmdline[1] in self.available_commands():
            cmd = self.commands[cmdline[1]]
            # Remove whitespaces from __doc__ lines
            desc = '\n'.join(map(str.strip, cmd['doc'].split('\n')))
            # Command name + module
            title = '* ' + cmdline[1] + ' (' + cmd['module'] + ')'
            out = (title, '', desc)

        else:
            # Create dict with module name as key and list of commands as value
            cmd_map = {}
            for cmd_name in self.available_commands():
                cmd = self.commands[cmd_name]
                mod_name = cmd['module']

                if not mod_name in cmd_map:
                    cmd_map[mod_name] = []

                cmd_map[mod_name].append(cmd_name)

            out = ['List of available Ludolph commands:']
            for mod_name, cmd_names in cmd_map.items():
                out.append('\n * ' + mod_name + ' * ')
                for name in cmd_names:
                    cmd = self.commands[name]
                    try:
                        # First line of __doc__
                        desc = cmd['doc'].split('\n')[0]
                        # Lowercase first char and remove trailing dot
                        desc = desc[0].lower() + desc[1:].rstrip('.')
                    except IndexError:
                        desc = ''
                    # Append line of command + description
                    out.append('\t* %s - %s' % (name, desc))

            out.append('\nUse "help <command>" for more information about the command usage')

        return '\n'.join(out)

    @command
    def version(self, msg):
        """
        Display Ludolph version.

        Usage: version
        """
        return 'Version: ' + VERSION

    @command
    def about(self, msg):
        """
        Details about this project.

        Usage: about
        """
        return ABOUT.strip()

    @admin_required
    @command
    def roster_list(self, msg):
        """
        List of users on Ludolph's roster (admin only).

        Usage: roster-list
        """
        roster = self.client_roster
        out = []

        for i in roster.keys():
            out.append((str(i), roster[i]['subscription'],))

        return str(tabulate(out, headers=['JID', 'subscription'], tablefmt=TABLEFMT))

    @admin_required
    @parameter_required(1)
    @command
    def roster_remove(self, msg, user):
        """
        Remove user from Ludolph's roster (admin only).

        Usage: roster-remove <JID>
        """
        if user in self.client_roster.keys():
            self.send_presence(pto=user, ptype='unsubscribe')
            self.del_roster_item(user)
            return 'User ' + user + ' removed from roster'
        else:
            return 'User ' + user + ' cannot be removed from roster'

    @command
    def uptime(self, msg):
        """
        Show Ludolph uptime.

        Usage: uptime
        """
        u = time.time() - self._start_time
        m, s = divmod(u, 60)
        h, m = divmod(m, 60)
        d, h = divmod(h, 24)

        return 'up %d days, %d hours, %d minutes, %d seconds' % (d, h, m, s)

    @admin_required
    @parameter_required(1)
    @command
    def muc_invite(self, msg, user):
        """
        Invite user to multi-user chat room (admin only).

        Usage: muc-invite <JID>
        """
        if not self.room:
            return 'MUC room disabled'

        self.muc.invite(self.room, user)

        return 'Inviting %s to MUC room %s' % (user, self.room)

    @command
    def muc_invite_me(self, msg):
        """
        Invite yourself to multi-user chat room.

        Usage: muc-invite-me
        """
        if not self.room:
            return 'MUC room disabled'

        me = self._get_jid(msg).bare
        self.muc.invite(self.room, me)

        return 'Inviting %s to MUC room %s' % (me, self.room)
