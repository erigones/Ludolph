"""
Ludolph: Monitoring Jabber bot
Copyright (C) 2012-2015 Erigones, s. r. o.
This file is part of Ludolph.

See the file LICENSE for copying permission.
"""
import time
import logging
import os
import imghdr
from sleekxmpp.exceptions import XMPPError
from glob import iglob

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

    def _get_avatar_dirs(self):
        """ Get list of directories where are avatars stored """
        avatar_dir = self.config.get('avatar_dir', None)
        default_avatar_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'avatars')

        if avatar_dir:
            return (avatar_dir, default_avatar_dir)
        else:
            return (default_avatar_dir,)

    @staticmethod
    def _get_avatar_allowed_extensions():
        """ Get list of extensions that are allowed for avatars """
        return ('.png', '.jpg', '.jpeg', '.gif')

    # noinspection PyUnusedLocal
    @admin_required
    @command
    def avatar_list(self, msg):
        """
        List available avatars for Ludolph

        Usage: avatar-list
        """
        files = []
        for avatar_dir in self._get_avatar_dirs():

            if os.path.isdir(avatar_dir):

                for file_type in Base._get_avatar_allowed_extensions():
                    for avatar in iglob(os.path.join(avatar_dir, '*' + file_type)):
                        files.append(os.path.basename(avatar))
            else:
                logger.warning('Avatars directory: %s does not exists.' % avatar_dir)
                continue

        if files:
            return 'List of available avatars: %s' % ', '.join(files)
        else:
            return 'No avatars were found... :('

    # noinspection PyUnusedLocal
    @admin_required
    @parameter_required(1)
    @command
    def avatar_set(self, msg, avatar_name):
        """
        Set avatar for Ludolph

        Usage: avatar-set <avatar>
        """
        if os.path.splitext(avatar_name)[1] not in Base._get_avatar_allowed_extensions():
            return 'ERROR: You have requested file that is not supported.'

        user = self.xmpp.get_jid(msg)
        avatar_file = None

        available_avatar_directories = self._get_avatar_dirs()
        for avatar_dir in available_avatar_directories:
            # Create full path to file requested by user
            avatar_file = os.path.join(avatar_dir, avatar_name)
            # Split absolute path for check if user is not trying to jump outside allowed dirs
            path, name = os.path.split(os.path.abspath(avatar_file))

            if path not in available_avatar_directories:
                return 'ERROR: You are not allowed to set avatar outside defined directories.'

            try:
                avatar_file = open(avatar_file)
            except (OSError, IOError):
                avatar_file = None
            else:
                break

        if not avatar_file:
            return 'ERROR: Avatar "%s" have not been found.\n' \
                   'You can try list available avatars with command: **avatar-list**' % avatar_name
        else:
            self.xmpp.msg_send(user, 'I have found selected avatar, changing it might take few seconds...')

        avatar = avatar_file.read()
        avatar_type = 'image/%s' % imghdr.what('', avatar)
        avatar_id = self.xmpp.plugin['xep_0084'].generate_id(avatar)
        avatar_bytes = len(avatar)
        avatar_file.close()

        used_xep84 = False
        try:
            logger.debug('Publish XEP-0084 avatar data')
            self.xmpp.plugin['xep_0084'].publish_avatar(avatar)
            used_xep84 = True
        except XMPPError as e:
            logger.error('Could not publish XEP-0084 avatar: %s' % e.text)
            return 'ERROR: Could not publish selected avatar'

        try:
            logger.debug('Publish XEP-0153 avatar vCard data')
            self.xmpp.plugin['xep_0153'].set_avatar(avatar=avatar, mtype=avatar_type)
        except XMPPError as e:
            logger.error('Could not publish XEP-0153 vCard avatar: %s' % e.text)
            return 'ERROR: Could not set vCard avatar'

        self.xmpp.msg_send(user, 'Almost done, please be patient')

        if used_xep84:
            try:
                logger.debug('Advertise XEP-0084 avatar metadata')
                self.xmpp['xep_0084'].publish_avatar_metadata([
                    {'id': avatar_id,
                     'type': avatar_type,
                     'bytes': avatar_bytes}
                ])
            except XMPPError as e:
                logger.error('Could not publish XEP-0084 metadata: %s' % e.text)
                return 'ERROR: Could not publish avatar metadata'

        return 'Avatar has been changed :)'

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
