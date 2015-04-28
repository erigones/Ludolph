"""
Ludolph: Monitoring Jabber Bot
Copyright (C) 2012-2015 Erigones, s. r. o.
This file is part of Ludolph.

See the LICENSE file for copying permission.
"""
from logging import getLogger
from functools import wraps
from collections import namedtuple
import shlex

from ludolph.utils import AttrDict

__all__ = ('CommandError', 'command', 'parameter_required')

logger = getLogger(__name__)


class CommandError(Exception):
    """
    Send a standard error message to user.
    """
    pass


class CommandPermissions(AttrDict):
    """
    Holds individual command permissions.
    """
    pass  # FIXME: Change to namedtuple after removing @admin_required decorator


class Command(namedtuple('Command', ('name', 'fun_name', 'module', 'doc', 'perms'))):
    """
    Ludolph command wrapper.
    """
    def __str__(self):
        return '%s.%s' % (self.module, self.fun_name)

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, self)

    def get_fun(self, bot):
        """Get command bound method from plugin"""
        return getattr(bot.plugins[self.module], self.fun_name)

    def is_jid_permitted_to_run(self, xmpp, jid):
        """Return True if user is allowed to run the command"""
        perms = self.perms

        for perm, check in ((perms.user_required, xmpp.is_jid_user),
                            (perms.admin_required, xmpp.is_jid_admin),
                            (perms.room_user_required, xmpp.is_jid_room_user),
                            (perms.room_admin_required, xmpp.is_jid_room_admin)):
            if perm and not check(jid):
                return False

        return True


class Commands(dict):
    """
    Command names to (name, module, doc) mapping.
    """
    _cache = None  # Cached sorted list of commands

    def reset(self):
        """Used before bot reload"""
        logger.info('Reinitializing commands')
        self.clear()

    def all(self, reset=False):
        """List of all available bot commands"""
        if self._cache is None or reset:
            self._cache = sorted(self.keys())

        return self._cache

    def display(self):
        """Return list of available commands suitable for logging output"""
        return ['%s [%s]' % (name, cmd.module) for name, cmd in self.items()]

    def get_command(self, cmdstr):
        """Find text in available commands and return command tuple"""
        if not cmdstr:
            return None

        if cmdstr in self.all():
            cmd = self[cmdstr]
        else:
            for key in self.all():
                if key.startswith(cmdstr):
                    cmd = self[key]
                    break
            else:
                return None

        return cmd


COMMANDS = Commands()  # command : (name, fun_name, module, doc, perms)


# noinspection PyShadowingNames
def command(func=None, stream_output=False, reply_output=True, user_required=True, admin_required=False,
            room_user_required=False, room_admin_required=False):
    """
    Decorator for registering available commands.
    """
    def command_decorator(fun):
        # Create command name - skip methods which start with underscore
        if fun.__name__.startswith('_'):
            logger.error('Ignoring command "%s" from plugin "%s" because it starts with underscore',
                         fun.__name__, fun.__module__)
            return None

        name = fun.__name__.replace('_', '-')

        # Check if command exists
        if name in COMMANDS:
            logger.critical('Command "%s" from plugin "%s" overlaps with existing command from module "%s"',
                            name, fun.__module__, COMMANDS[name].module)
            return None

        # Save documentation
        if fun.__doc__:
            doc = fun.__doc__.strip()
        else:
            logger.warning('Missing documentation for command "%s"', name)
            doc = ''

        # Save module and method name
        logger.debug('Registering command "%s" from plugin "%s"', name, fun.__module__)
        perms = CommandPermissions(user_required=user_required, admin_required=admin_required,
                                   room_user_required=room_user_required, room_admin_required=room_admin_required)
        cmd = Command(name, fun.__name__, fun.__module__, doc, perms)
        COMMANDS[name] = cmd

        @wraps(fun)
        def wrap(obj, msg, *args, **kwargs):
            xmpp = obj.xmpp
            user = xmpp.get_jid(msg)
            success = False
            reply = msg.get_reply_output(default=reply_output, set_default=True)  # Used for scheduled "at" jobs
            stream = msg.get_stream_output(default=stream_output, set_default=True)  # Not used

            if cmd.is_jid_permitted_to_run(xmpp, user):
                logger.info('User "%s" requested command "%s" (%s) [stream=%s] [reply=%s]',
                            user, msg['body'], cmd, stream, reply)

                # Parse optional parameters
                if fun.__defaults__:
                    required_pos = len(args) + 1
                    optional_end = required_pos + len(fun.__defaults__)
                    optional_args = shlex.split(msg['body'].strip())[required_pos:optional_end]
                    args += tuple(optional_args)

                # Reply with function output
                try:
                    response = fun(obj, msg, *args, **kwargs)

                    if stream:
                        if reply:
                            _out = []
                            for line in response:
                                _out.append(line)
                                xmpp.msg_reply(msg, line, preserve_msg=True)
                        else:
                            _out = response

                        out = '\n'.join(_out)
                    else:
                        out = response
                except CommandError as e:
                    out = 'ERROR: %s' % e
                except Exception as e:
                    logger.exception(e)
                    out = 'ERROR: Command failed due to internal programming error: %s' % e
                else:
                    success = True
                    logger.debug('Command output: "%s"', out)
            else:
                logger.warning('Unauthorized command "%s" (%s) from "%s"', msg['body'], cmd, user)
                out = 'ERROR: Permission denied'

            if reply:
                # No need to send a reply, everything was send during stream_output command processing
                if stream and success:
                    return out

                xmpp.msg_reply(msg, out)

            return out

        return wrap

    if func and hasattr(func, '__call__'):
        return command_decorator(func)
    else:
        return command_decorator


def parameter_required(count, internal=False):
    """
    Decorator for checking required command parameters.
    """
    if hasattr(count, '__call__'):  # fun is count and count is 1 :)
        func = count
        count = 1
    else:
        func = None

    def parameter_required_decorator(fun):
        @wraps(fun)
        def wrap(obj, msg, *args, **kwargs):
            if internal:
                # Command parameters are args
                params = args
            else:
                # Try to get command parameters
                params = shlex.split(msg['body'].strip())[1:]

            # Check if required parameters are set and not empty
            if len(params) < count or (count and not all(params[:count])):
                user = obj.xmpp.get_jid(msg)
                logger.warning('Missing parameter in command "%s" from user "%s"', msg['body'], user)
                obj.xmpp.msg_reply(msg, 'ERROR: Missing parameter')
                return None
            else:
                if not internal:
                    params.extend(args)
                return fun(obj, msg, *params, **kwargs)

        return wrap

    if func:
        return parameter_required_decorator(func)
    else:
        return parameter_required_decorator


def admin_required(fun):
    """
    Decorator for admin only commands. [DEPRECATED]
    """
    name = fun.__name__.replace('_', '-')
    logger.warning('The @admin_required decorator on command "%s" in plugin %s is due to be deprecated. '
                   'Use the admin_required parameter in the @command decorator instead.', name, fun.__module__)

    try:
        COMMANDS[name].perms.admin_required = True
    except KeyError:
        logger.critical('Command "%s" from plugin "%s" is not registered. Wrong decorator order?', name, fun.__module__)
        return None

    @wraps(fun)
    def wrap(obj, msg, *args, **kwargs):
        return fun(obj, msg, *args, **kwargs)

    return wrap
