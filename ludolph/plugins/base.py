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
from sleekxmpp.exceptions import XMPPError, IqError
from glob import iglob

# noinspection PyPep8Naming
from ludolph import __doc__ as ABOUT
from ludolph import __version__
from ludolph.command import CommandError, MissingParameter, command
from ludolph.web import webhook, request, abort
from ludolph.utils import pluralize
from ludolph.plugins.plugin import LudolphPlugin

logger = logging.getLogger(__name__)


class Base(LudolphPlugin):
    """
    Ludolph jabber bot base commands.
    """
    __version__ = __version__
    _avatar_allowed_extensions = frozenset(['.png', '.jpg', '.jpeg', '.gif'])
    _status_show_types = frozenset(['online', 'away', 'chat', 'dnd', 'xa'])  # online is a fake type translated to None
    _help_cache = None
    _cron_required = ('at', 'remind')
    _reminder = '__You have asked me to remind you:__ '

    def __post_init__(self):
        # Disable at command if cron is disabled
        if not self.xmpp.cron:
            for i in self._cron_required:
                self.xmpp.commands.pop(i)

        # Reset help command cache
        self._help_cache = None
        # Override fallback message handler
        self.xmpp.fallback_message = self._fallback_message

    def __destroy__(self):
        # Recover original fallback message handler
        self.xmpp.fallback_message = self.xmpp.original_fallback_message

    def _fallback_message(self, msg, cmd_name):
        """Fallback message handler called in case the command does not exist"""
        self.xmpp.msg_reply(msg, 'Sorry, I don\'t understand __"%s"__\n'
                                 'Please type **help** for more info' % cmd_name)

    def _help_all(self):
        """Return list of all commands organized by plugins"""
        if self._help_cache is None:
            # Create dict with module name as key and list of commands as value
            xmpp = self.xmpp
            cmd_map = {}

            for cmd_name in xmpp.commands.all():
                cmd = xmpp.commands[cmd_name]
                mod_name = cmd.module

                if mod_name not in cmd_map:
                    cmd_map[mod_name] = []

                cmd_map[mod_name].append(cmd)

            out = ['List of available **%s** commands:' % xmpp.nick]

            for mod_name, plugin in xmpp.plugins.items():  # The plugins dict knows the plugin order
                try:
                    commands = cmd_map[mod_name]
                except KeyError:
                    continue

                # Item: module name
                if plugin.__version__:
                    version = '^^%s^^' % plugin.__version__
                else:
                    version = ''

                out.append('\n* %s %s\n' % (mod_name, version))

                for cmd in commands:
                    try:
                        # First line of __doc__
                        desc = cmd.doc.split('\n')[0].replace(xmpp.__class__.nick, xmpp.nick)
                        # Lowercase first char and remove trailing dot
                        desc = ' - ' + desc[0].lower() + desc[1:].rstrip('.')
                    except IndexError:
                        desc = ''

                    # SubItem: line of command + description
                    out.append('  * **%s**%s' % (cmd.name, desc))

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
            xmpp = self.xmpp
            cmd = xmpp.commands.get_command(cmdstr)

            if cmd:
                # Remove whitespaces from __doc__ lines
                desc = '\n'.join(map(str.strip, cmd.doc.split('\n')))
                # **Command name** (module) + desc
                return '**%s** (%s)\n\n%s' % (cmd.name, cmd.module, desc.replace(xmpp.__class__.nick, xmpp.nick))

        return self._help_all()

    # noinspection PyUnusedLocal
    @command
    def version(self, msg, plugin=None):
        """
        Display version of Ludolph or registered plugin.

        Usage: version [plugin]
        """
        if plugin:
            mod, obj = self.xmpp.plugins.get_plugin(plugin)

            if mod:
                return '**%s** version: %s' % (mod, obj.get_version())
            else:
                raise CommandError('**%s** isn\'t a Ludolph plugin. Check help for available plugins.' % plugin)

        return '**Ludolph** version: %s' % self.get_version()

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    @command
    def about(self, msg):
        """
        Details about this project.

        Usage: about
        """
        return ABOUT.strip()

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
    def message(self, msg, jid, text):
        """
        Send new XMPP message to user/room.

        Usage: message <JID> <text>
        """
        return self._message_send(jid, text)

    # noinspection PyUnusedLocal
    @command(admin_required=True)
    def broadcast(self, msg, text):
        """
        Send private message to every user in roster (admin only).

        Usage: broadcast <message>
        """
        return 'Message broadcasted to %dx users.' % self.xmpp.msg_broadcast(text)

    def _set_status(self, show, status=None):
        """Send presence status"""
        if show not in self._status_show_types:
            raise CommandError('Invalid status type')

        if show == 'online':
            show = None

        try:
            self.xmpp.send_presence(pstatus=status, pshow=show)
        except IqError as e:
            raise CommandError('Status update failed: __%s__' % getattr(e, 'condition', str(e)))

    # noinspection PyUnusedLocal
    @command(admin_required=True)
    def status(self, msg, show, status=None):
        """
        Set Ludolph's status (admin only).

        Usage: status {online|away|chat|dnd|xa} [status message]
        """
        self._set_status(show, status=status)

        return 'Status updated'

    def _roster_list(self):
        """List users on Ludolph's roster (admin only)"""
        roster = self.xmpp.client_roster

        return '\n'.join(['%s\t%s' % (i, roster[i]['subscription']) for i in roster])

    def _roster_del(self, user):
        """Remove user from Ludolph's roster (admin only)"""
        if user in self.xmpp.client_roster:
            self.xmpp.send_presence(pto=user, ptype='unsubscribe')
            self.xmpp.del_roster_item(user)

            return 'User **%s** removed from roster' % user
        else:
            return 'User **%s** cannot be removed from roster' % user

    # noinspection PyUnusedLocal
    @command(admin_required=True)
    def roster(self, msg, action=None, user=None):
        """
        List and manage users on Ludolph's roster (admin only).

        List users on Ludolph's roster.
        Usage: roster

        Remove user from Ludolph's roster
        Usage: roster del <JID>
        """
        if action == 'del':
            if user:
                return self._roster_del(user)
            else:
                raise MissingParameter

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

    @command(admin_required=True)
    def avatar(self, msg, action=None, avatar_name=None):
        """
        List available avatars or set an avatar for Ludolph (admin only).

        List available avatars for Ludolph.
        Usage: avatar

        Set avatar for Ludolph.
        Usage: avatar set <avatar>
        """
        if action == 'set':
            if avatar_name:
                return self._avatar_set(msg, avatar_name)
            else:
                raise MissingParameter

        return self._avatar_list()

    def _at_list(self, msg, reminder=False):
        """List all scheduled jobs"""
        crontab = self.xmpp.cron.crontab
        user = self.xmpp.get_jid(msg)

        if reminder:
            display_job = lambda cronjob: cronjob.onetime and user == cronjob.owner \
                and cronjob.command.split(' ')[:2] == ['message', user]

            out = ['**%s** [%s] __%s__' % (name, job.schedule,
                                           ' '.join(job.command.split(' ')[2:]).replace(self._reminder + ' ', ''))
                   for name, job in crontab.items() if display_job(job)]
        else:

            if self.xmpp.is_jid_admin(user):
                display_job = lambda cronjob: cronjob.onetime
            else:
                display_job = lambda cronjob: cronjob.onetime and user == cronjob.owner

            out = ['**%s** [%s] (%s) __%s__' % (name, job.schedule, job.owner, job.command)
                   for name, job in crontab.items() if display_job(job)]

        count = len(out)
        out.append('\n**%d** %s scheduled' % (count, pluralize(count, 'job is', 'jobs are')))

        return '\n'.join(out)

    def _at_del(self, msg, name):
        """Remove scheduled job"""
        try:
            job_id = int(name)
        except (ValueError, TypeError):
            raise CommandError('Invalid job ID')

        crontab = self.xmpp.cron.crontab
        job = crontab.get(job_id, None)

        if job and job.onetime:
            user = self.xmpp.get_jid(msg)

            if job.owner == user or self.xmpp.is_jid_admin(user):
                crontab.delete(job_id)
                logger.info('Deleted one-time cron jobs: %s', job.display())

                return 'Scheduled job ID **%s** deleted' % job_id
            else:
                raise CommandError('Permission denied')

        raise CommandError('Non-existent job ID')

    def _at_add(self, msg, schedule, cmd_name, *cmd_args, **job_kwargs):
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
        user = self.xmpp.get_jid(msg)

        if not cmd.is_jid_permitted_to_run(self.xmpp, user):
            raise CommandError('Permission denied')

        # Create message (the only argument needed for command) with body representing the whole command
        body = ' '.join([cmd.name] + ["%s" % i for i in cmd_args])
        msg = self.xmpp.msg_copy(msg, body=body)
        job = self.xmpp.cron.crontab.add_at(cmd.get_fun(self.xmpp), dt, msg, user, **job_kwargs)
        logger.info('Registered one-time cron job: %s', job.display())

        return 'Scheduled job ID **%s** scheduled at %s' % (job.name, job.schedule)

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
        if not self.xmpp.cron:
            raise CommandError('Cron support is disabled in Ludolph configuration file')

        args_count = len(args)

        if args_count > 0:
            action = args[0]

            if action == 'add':
                if args_count < 3:
                    raise MissingParameter
                else:
                    return self._at_add(msg, *args[1:])
            elif action == 'del':
                if args_count < 2:
                    raise MissingParameter
                else:
                    return self._at_del(msg, args[1])
            else:
                raise CommandError('Invalid action')

        return self._at_list(msg)

    @command
    def remind(self, msg, *args):
        """
        List, add, or delete reminders.

        List all scheduled reminders.
        Usage: remind

        Schedule reminder at specific time and date.
        Usage: remind add +minutes <message>
        Usage: remind add Y-m-d-H-M <message>

        Remove reminder from queue of scheduled reminders.
        Usage: remind del <reminder ID>
        """
        args_count = len(args)

        if args_count > 0:
            action = args[0]

            if action == 'add':
                if args_count < 2:
                    raise MissingParameter
                else:
                    return self._at_add(msg, *(args[1], 'message', self.xmpp.get_jid(msg), self._reminder) + args[2:],
                                        at_reply_output=False)
            elif action == 'del':
                if args_count < 2:
                    raise MissingParameter
                else:
                    return self._at_del(msg, args[1])
            else:
                raise CommandError('Invalid action')

        return self._at_list(msg, reminder=True)

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
