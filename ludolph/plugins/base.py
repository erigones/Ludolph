"""
Ludolph: Monitoring Jabber bot
Copyright (C) 2012-2014 Erigones s. r. o.
This file is part of Ludolph.

See the file LICENSE for copying permission.
"""
import time
import logging

# noinspection PyPep8Naming
from ludolph.__init__ import __doc__ as ABOUT
# noinspection PyPep8Naming
from ludolph.__init__ import __version__ as VERSION
from ludolph.command import command, parameter_required, admin_required
from ludolph.web import webhook, request, abort
from ludolph.plugins.plugin import LudolphPlugin

logger = logging.getLogger(__name__)


class Base(LudolphPlugin):
    """
    Ludolph jabber bot base commands.
    """
    # noinspection PyUnusedLocal
    @command
    def help(self, msg, cmdstr=None):
        """
        Show this help.

        Usage: help [command]
        """
        # Global help or command help?
        if cmdstr:
            cmd = self.xmpp.commands.get_command(cmdstr)
            if cmd:
                # Remove whitespaces from __doc__ lines
                desc = '\n'.join(map(str.strip, cmd[-1].split('\n')))
                # **Command name** (module) + desc
                return '**%s** (%s)\n\n%s' % (cmd[0], cmd[1], desc)

        # Create dict with module name as key and list of commands as value
        cmd_map = {}
        for cmd_name in self.xmpp.commands.all():
            cmd = self.xmpp.commands[cmd_name]
            mod_name = cmd[1]

            if not mod_name in cmd_map:
                cmd_map[mod_name] = []

            cmd_map[mod_name].append(cmd_name)

        out = ['List of available Ludolph commands:']

        for mod_name, cmd_names in cmd_map.items():
            # Item: module name
            out.append('\n* %s\n' % mod_name)

            for name in cmd_names:
                try:
                    # First line of __doc__
                    desc = self.xmpp.commands[name][-1].split('\n')[0]
                    # Lowercase first char and remove trailing dot
                    desc = ' - ' + desc[0].lower() + desc[1:].rstrip('.')
                except IndexError:
                    desc = ''

                # SubItem: line of command + description
                out.append('  * **%s**%s' % (name, desc))

        out.append('\nUse "help <command>" for more information about the command usage')

        return '\n'.join(out)

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    @command
    def version(self, msg):
        """
        Display Ludolph version.

        Usage: version
        """
        return 'Version: ' + VERSION

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    @command
    def about(self, msg):
        """
        Details about this project.

        Usage: about
        """
        return ABOUT.strip()

    # noinspection PyUnusedLocal
    @admin_required
    @command
    def roster_list(self, msg):
        """
        List of users on Ludolph's roster (admin only).

        Usage: roster-list
        """
        roster = self.xmpp.client_roster

        return '\n'.join(['%s\t%s' % (i, roster[i]['subscription']) for i in roster])

    # noinspection PyUnusedLocal
    @admin_required
    @parameter_required(1)
    @command
    def roster_remove(self, msg, user):
        """
        Remove user from Ludolph's roster (admin only).

        Usage: roster-remove <JID>
        """
        if user in self.xmpp.client_roster:
            self.xmpp.send_presence(pto=user, ptype='unsubscribe')
            self.xmpp.del_roster_item(user)
            return 'User **' + user + '** removed from roster'
        else:
            return 'User **' + user + '** cannot be removed from roster'

    # noinspection PyUnusedLocal
    @command
    def uptime(self, msg):
        """
        Show Ludolph uptime.

        Usage: uptime
        """
        # noinspection PyProtectedMember
        u = time.time() - self.xmpp._start_time
        m, s = divmod(u, 60)
        h, m = divmod(m, 60)
        d, h = divmod(h, 24)

        return 'up %d days, %d hours, %d minutes, %d seconds' % (d, h, m, s)

    @admin_required
    @command
    def muc_invite(self, msg, user=None):
        """
        Invite user or yourself to multi-user chat room (admin only).

        Usage: muc-invite [JID]
        """
        if not self.xmpp.room:
            return 'ERROR: MUC room disabled'

        if not user:
            user = self.xmpp.get_jid(msg)

        self.xmpp.muc.invite(self.xmpp.room, user)

        return 'Inviting **%s** to MUC room %s' % (user, self.xmpp.room)

    @webhook('/')
    def index(self):
        """
        Default web page.
        """
        return ABOUT

    @webhook('/ping')
    def ping(self):
        """
        Ping-pong.
        """
        return 'pong'

    @webhook('/broadcast', methods=('POST',))
    def broadcast(self):
        """
        Send private message to every user in roster.
        """
        msg = request.forms.get('msg', None)

        if not msg:
            logger.warning('Missing msg parameter in broadcast request')
            abort(400, 'Missing msg parameter')

        for jid in self.xmpp.client_roster:
            self.xmpp.msg_send(jid, msg)

        return 'Message sent (%dx)' % len(self.xmpp.client_roster)

    @webhook('/room', methods=('POST',))
    def roomtalk(self):
        """
        Send message to chat room.
        """
        if not self.xmpp.room:
            logger.warning('Multi-user chat support is disabled (room request)')
            abort(400, 'MUC disabled')

        msg = request.forms.get('msg', None)

        if not msg:
            logger.warning('Missing msg parameter in room request')
            abort(400, 'Missing msg parameter')

        self.xmpp.msg_send(self.xmpp.room, msg, mtype='groupchat')

        return 'Message sent'
