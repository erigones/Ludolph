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
from datetime import datetime, timedelta
from sleekxmpp.exceptions import XMPPError
from glob import iglob

# noinspection PyPep8Naming
from ludolph import __doc__ as ABOUT
# noinspection PyPep8Naming
from ludolph import __version__
from ludolph.command import CommandError, command, parameter_required, admin_required
from ludolph.web import webhook, request, abort
from ludolph.utils import pluralize
from ludolph.plugins.plugin import LudolphPlugin

logger = logging.getLogger(__name__)


class Base(LudolphPlugin):
    """
    Ludolph jabber bot base commands.
    """
    _avatar_allowed_extensions = ('.png', '.jpg', '.jpeg', '.gif')
    __version__ = __version__

    def __init__(self, xmpp, config, **kwargs):
        super(Base, self).__init__(xmpp, config, **kwargs)
        self._help_cache = None

    def _help_all(self):
        """Return list of all commands organized by plugins"""
        if self._help_cache is None:
            # Create dict with module name as key and list of commands as value
            cmd_map = {}
            for cmd_name in self.xmpp.commands.all():
                cmd = self.xmpp.commands[cmd_name]
                mod_name = cmd.module

                if mod_name not in cmd_map:
                    cmd_map[mod_name] = []

                cmd_map[mod_name].append(cmd_name)

            out = ['List of available Ludolph commands:']

            for mod_name in self.xmpp.plugins:  # The plugins dict knows the plugin order
                try:
                    cmd_names = cmd_map[mod_name]
                except KeyError:
                    continue

                # Item: module name
                out.append('\n* %s\n' % mod_name)

                for name in cmd_names:
                    try:
                        # First line of __doc__
                        desc = self.xmpp.commands[name].doc.split('\n')[0]
                        # Lowercase first char and remove trailing dot
                        desc = ' - ' + desc[0].lower() + desc[1:].rstrip('.')
                    except IndexError:
                        desc = ''

                    # SubItem: line of command + description
                    out.append('  * **%s**%s' % (name, desc))

            out.append('\nUse "help <command>" for more information about the command usage')
            self._help_cache = '\n'.join(out)

        return self._help_cache

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
                desc = '\n'.join(map(str.strip, cmd.doc.split('\n')))
                # **Command name** (module) + desc
                return '**%s** (%s)\n\n%s' % (cmd.name, cmd.module, desc)

        return self._help_all()

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    @command
    def version(self, msg, plugin=None):
        """
        Display version of Ludolph or registered plugin.

        Display Ludolph version.
        Usage: version

        Display Ludolph's registered plugin version.
        Usage: version [plugin]
        """
        if plugin:
            if plugin in self.xmpp.plugins:
                return '**%s** version: %s' % (plugin, self.xmpp.plugins[plugin].get_version())
            return '**%s** isnt Ludolph plugin. Check help for available plugins.' % plugin
        return '**Ludolph** version: %s' % self.get_version()

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    @command
    def about(self, msg):
        """
        Details about this project.

        Usage: about
        """
        return ABOUT.strip()

    def _message_send(self, jid, msg):
        """Send new xmpp message. Used by message command and /message webhook"""
        if jid == self.xmpp.room:
            mtype = 'groupchat'
        elif jid in self.xmpp.client_roster:
            mtype = 'normal'
        else:
            raise CommandError('User "%s" not in roster' % jid)

        logger.info('Sending message to "%s"', jid)
        logger.debug('\twith body: "%s"', msg)
        self.xmpp.msg_send(jid, msg, mtype=mtype)

        return 'Message sent to **%s**' % jid

    # noinspection PyUnusedLocal
    @command
    @parameter_required(2)
    def message(self, msg, jid, *args):
        """
        Send new XMPP message to user/room.

        Usage: message <JID> <text>
        """
        return self._message_send(jid, ' '.join(args))

    def _roster_list(self):
        """List users on Ludolph's roster (admin only)"""
        roster = self.xmpp.client_roster

        return '\n'.join(['%s\t%s' % (i, roster[i]['subscription']) for i in roster])

    # noinspection PyUnusedLocal
    @parameter_required(1, internal=True)
    def _roster_del(self, msg, user):
        """Remove user from Ludolph's roster (admin only)"""
        if user and user in self.xmpp.client_roster:
            self.xmpp.send_presence(pto=user, ptype='unsubscribe')
            self.xmpp.del_roster_item(user)

            return 'User **%s** removed from roster' % user
        else:
            return 'User **%s** cannot be removed from roster' % user

    @admin_required
    @command
    def roster(self, msg, action=None, user=None):
        """
        List and manage users on Ludolph's roster (admin only).

        List users on Ludolph's roster.
        Usage: roster

        Remove user from Ludolph's roster
        Usage: roster del <JID>
        """
        if action == 'del':
            return self._roster_del(msg, user)

        return self._roster_list()

    def _get_avatar_dirs(self):
        """Get list of directories where avatars are stored."""
        avatar_dir = self.config.get('avatar_dir', None)
        default_avatar_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'avatars')

        if avatar_dir:
            return avatar_dir, default_avatar_dir
        else:
            return default_avatar_dir,

    def _avatar_list(self):
        """List available avatars for Ludolph (admin only)"""
        files = []

        for avatar_dir in self._get_avatar_dirs():
            if os.path.isdir(avatar_dir):
                for file_type in self._avatar_allowed_extensions:
                    for avatar in iglob(os.path.join(avatar_dir, '*' + file_type)):
                        files.append(os.path.basename(avatar))
            else:
                logger.warning('Avatars directory: %s does not exists.' % avatar_dir)
                continue

        if files:
            return 'List of available avatars: %s' % ', '.join(files)
        else:
            return 'No avatars were found... :('

    @parameter_required(1, internal=True)
    def _avatar_set(self, msg, avatar_name):
        """Set avatar for Ludolph (admin only)"""
        if os.path.splitext(avatar_name)[-1] not in self._avatar_allowed_extensions:
            raise CommandError('You have requested a file that is not supported')

        avatar = None
        available_avatar_directories = self._get_avatar_dirs()

        for avatar_dir in available_avatar_directories:
            # Create full path to file requested by user
            avatar_file = os.path.join(avatar_dir, avatar_name)
            # Split absolute path for check if user is not trying to jump outside allowed dirs
            path, name = os.path.split(os.path.abspath(avatar_file))

            if path not in available_avatar_directories:
                raise CommandError('You are not allowed to set avatar outside defined directories')

            try:
                with open(avatar_file, 'rb') as f:
                    avatar = f.read()
            except (OSError, IOError):
                avatar = None
            else:
                break

        if not avatar:
            raise CommandError('Avatar "%s" has not been found.\n'
                               'You can list available avatars with the command: **avatar-list**' % avatar_name)
        else:
            self.xmpp.msg_reply(msg, 'I have found the selected avatar, changing it might take few seconds...',
                                preserve_msg=True)

        avatar_type = 'image/%s' % imghdr.what('', avatar)
        avatar_id = self.xmpp.plugin['xep_0084'].generate_id(avatar)
        avatar_bytes = len(avatar)

        try:
            logger.debug('Publishing XEP-0084 avatar data')
            self.xmpp.plugin['xep_0084'].publish_avatar(avatar)
        except XMPPError as e:
            logger.error('Could not publish XEP-0084 avatar: %s' % e.text)
            raise CommandError('Could not publish selected avatar')

        try:
            logger.debug('Publishing XEP-0153 avatar vCard data')
            self.xmpp.plugin['xep_0153'].set_avatar(avatar=avatar, mtype=avatar_type)
        except XMPPError as e:
            logger.error('Could not publish XEP-0153 vCard avatar: %s' % e.text)
            raise CommandError('Could not set vCard avatar')

        self.xmpp.msg_reply(msg, 'Almost done, please be patient', preserve_msg=True)

        try:
            logger.debug('Advertise XEP-0084 avatar metadata')
            self.xmpp['xep_0084'].publish_avatar_metadata([{
                'id': avatar_id,
                'type': avatar_type,
                'bytes': avatar_bytes
            }])
        except XMPPError as e:
            logger.error('Could not publish XEP-0084 metadata: %s' % e.text)
            raise CommandError('Could not publish avatar metadata')

        return 'Avatar has been changed :)'

    @admin_required
    @command
    def avatar(self, msg, action=None, avatar_name=None):
        """
        List available avatars or set an avatar for Ludolph (admin only).

        List available avatars for Ludolph.
        Usage: avatar

        Set avatar for Ludolph.
        Usage: avatar set <avatar>
        """
        if action == 'set':
            return self._avatar_set(msg, avatar_name)

        return self._avatar_list()

    # noinspection PyUnusedLocal
    @admin_required
    @parameter_required(1)
    @command
    def broadcast(self, msg, *args):
        """
        Send private message to every user in roster.

        Usage: broadcast <message>
        """
        return 'Message broadcasted to %dx users.' % self.xmpp.msg_broadcast(' '.join(args))

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
            raise CommandError('MUC room disabled')

        if not user:
            user = self.xmpp.get_jid(msg)

        self.xmpp.muc.invite(self.xmpp.room, user)

        return 'Inviting **%s** to MUC room %s' % (user, self.xmpp.room)

    def _at_list(self):
        """List all scheduled jobs"""
        crontab = self.xmpp.cron.crontab
        out = ['**%s** [%s] (%s) __%s__' % (name, job.schedule, job.owner, job.command)
               for name, job in crontab.items() if job.onetime]
        count = len(out)
        out.append('\n**%d** %s scheduled' % (count, pluralize(count, 'job is', 'jobs are')))

        return '\n'.join(out)

    @parameter_required(1, internal=True)
    def _at_del(self, msg, name):
        """Remove scheduled job"""
        try:
            job_id = int(name)
        except ValueError:
            raise CommandError('Invalid job ID')

        crontab = self.xmpp.cron.crontab
        job = crontab.get(job_id, None)

        if job and job.onetime:
            admins = self.xmpp.admins
            user = self.xmpp.get_jid(msg)

            if job.owner == user or (not admins or user in admins):
                crontab.delete(job_id)
                logger.info('Deleted one-time cron jobs: %s', job.display())

                return 'Scheduled job ID **%s** deleted' % job_id
            else:
                raise CommandError('Permission denied')

        raise CommandError('Non-existent job ID')

    @parameter_required(2, internal=True)
    def _at_add(self, msg, schedule, cmd_name, *args):
        """Schedule command execution at specific time and date"""
        # Validate schedule
        schedule = str(schedule)

        if schedule.startswith('+'):
            try:
                dt = datetime.now() + timedelta(minutes=int(schedule))
            except ValueError:
                raise CommandError('Invalid date-time (required format: +<integer>)')
        else:
            try:
                dt = datetime.strptime(schedule, '%Y-%m-%d-%H-%M')
            except ValueError:
                raise CommandError('Invalid date-time (required format: YYYY-mm-dd-HH-MM)')

        # Validate command
        cmd = self.xmpp.commands.get_command(cmd_name)

        if not cmd:
            raise CommandError('Invalid command')

        # Check user permission
        admins = self.xmpp.admins
        user = self.xmpp.get_jid(msg)

        if cmd.fun.admin_required and admins and user not in admins:
            raise CommandError('Permission denied')

        # Create message (the only argument needed for command) with body representing the whole command
        body = ' '.join([cmd.cmd] + ["%s" % i for i in args])
        msg = self.xmpp.msg_copy(msg, body=body)
        job = self.xmpp.cron.crontab.add_at(cmd.get_fun(self.xmpp), dt, msg, user)
        logger.info('Registered one-time cron job: %s', job.display())

        return 'Scheduled job ID **%s** scheduled at %s' % (job.name, job.schedule)

    @parameter_required(0)
    @command
    def at(self, msg, *args):
        """
        List, add, or delete jobs for later execution.

        List all scheduled jobs.
        Usage: at

        Schedule command execution at specific time and date.
        Usage: at add +minutes <command> [command parameters...]
        Usage: at add Y-m-d-H-M <command> [command parameters...]

        Remove command from queue of scheduled jobs.
        Usage: at del <job ID>
        """
        if len(args) > 1:
            action = args[0]

            if action == 'add':
                return self._at_add(msg, *args[1:])
            elif action == 'del':
                return self._at_del(msg, args[1])

        return self._at_list()

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

    @webhook('/message', methods=('POST',))
    def send_msg(self):
        """
        Send xmpp message to user/room.
        """
        jid = request.forms.get('jid', None)

        if not jid:
            abort(400, 'Missing JID in message request')

        msg = request.forms.get('msg', '')

        try:
            return self._message_send(jid, msg)
        except CommandError as e:
            abort(400, str(e))

    @webhook('/broadcast', methods=('POST',))
    def broadcast_msg(self):
        """
        Send private message to every user in roster.
        """
        msg = request.forms.get('msg', None)

        if not msg:
            logger.warning('Missing msg parameter in broadcast request')
            abort(400, 'Missing msg parameter')

        return 'Message sent (%dx)' % self.xmpp.msg_broadcast(msg)

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
