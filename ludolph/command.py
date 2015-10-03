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
import inspect

__all__ = ('CommandError', 'PermissionDenied', 'MissingParameter', 'command')

logger = getLogger(__name__)


class CommandError(Exception):
    """
    Send a standard error message to user.
    """
    error_message = ''

    def __init__(self, msg=None):
        self.error_message = msg or self.error_message

    def __str__(self):
        return 'ERROR: %s' % self.error_message


class PermissionDenied(CommandError):
    error_message = 'Permission denied'


class MissingParameter(CommandError):
    error_message = 'Missing parameter'


CommandPermissions = namedtuple('CommandPermissions', ('user_required', 'admin_required', 'room_user_required',
                                                       'room_admin_required'))

CommandParameters = namedtuple('CommandParameters', ('args_count', 'kwargs_count', 'star_args'))


class Command(namedtuple('Command', ('name', 'fun_name', 'module', 'doc', 'perms', 'fun_spec'))):
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

    def get_args_from_msg_body(self, body):
        """Parse message body and return a list which can be used as *args parameter for this command"""
        fun_spec = self.fun_spec
        last_pos = fun_spec.args_count + fun_spec.kwargs_count - 1

        if last_pos < 0 and not fun_spec.star_args:  # Function has no custom arguments
            return []

        # Try to get command parameters (with command name removed)
        try:
            params = shlex.split(body)[1:]
        except ValueError:
            params = body.split()[1:]

        params_count = len(params)

        if fun_spec.args_count:  # Check if required arguments are set and not empty
            if params_count < fun_spec.args_count or not all(params[:fun_spec.args_count]):
                raise MissingParameter

        if fun_spec.star_args or last_pos >= params_count:
            return params
        else:
            return params[:last_pos] + [' '.join(params[last_pos:])]


class Commands(dict):
    """
    Command names to (name, module, doc) mapping.
    """
    _cache = None  # Cached sorted list of commands

    def pop(self, key, **kwargs):
        """Properly remove command from dict and cache"""
        cmd = super(Commands, self).pop(key, **kwargs)

        if cmd:
            logger.info('Deregistering command "%s" from plugin "%s"', cmd.name, cmd.module)
            if self._cache:
                try:
                    self._cache.remove(key)
                except ValueError:
                    pass

        return cmd

    def __setitem__(self, key, cmd):
        assert isinstance(cmd, Command), 'value must be an instance of %s' % Command.__class__.__name__
        assert key == cmd.name
        logger.debug('Registering command "%s" from plugin "%s"', cmd.name, cmd.module)
        super(Commands, self).__setitem__(key, cmd)

    def __delitem__(self, key):
        """Properly remove command from dict and cache"""
        if key in self:
            self.pop(key)
        else:
            raise KeyError(key)

    def reset(self, module=None):
        """Used before bot reload"""
        if module:
            logger.info('Deregistering commands from plugin: %s', module)
            for name, cmd in tuple(self.items()):  # Copy for python 3
                if cmd.module == module:
                    logger.debug('Deregistering command "%s" from plugin "%s"', name, cmd.module)
                    del self[name]
        else:
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

        cmdstr = cmdstr.lower()

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
            room_user_required=False, room_admin_required=False, parse_parameters=True):
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

        # Fetch command parameters (the method must accept at least two positional arguments - self and msg)
        arg_spec = inspect.getargspec(fun)

        if len(arg_spec.args) < 2:
            logger.critical('Command "%s" from plugin "%s" is missing required arguments', name, fun.__module__)
            return None
        else:
            if arg_spec.defaults:
                kwargs_count = len(arg_spec.defaults)
            else:
                kwargs_count = 0

            fun_spec = CommandParameters(len(arg_spec.args[2:]) - kwargs_count, kwargs_count, bool(arg_spec.varargs))

        # Save documentation
        if fun.__doc__:
            doc = fun.__doc__.strip()
        else:
            logger.warning('Missing documentation for command "%s"', name)
            doc = ''

        # Save module, method name and other command metadata
        perms = CommandPermissions(user_required=user_required, admin_required=admin_required,
                                   room_user_required=room_user_required, room_admin_required=room_admin_required)
        cmd = Command(name, fun.__name__, fun.__module__, doc, perms, fun_spec)
        COMMANDS[name] = cmd
        logger.debug('Registered command "%s" (%s) ::\n perms=%s\n fun_spec=%s', name, cmd, perms, fun_spec)

        @wraps(fun)
        def wrap(obj, msg, *args, **kwargs):
            xmpp = obj.xmpp
            user = xmpp.get_jid(msg)
            body = msg['body'].strip()
            success = False
            reply = msg.get_reply_output(default=reply_output, set_default=True)  # Used for scheduled "at" jobs
            stream = msg.get_stream_output(default=stream_output, set_default=True)  # Used by the commands plugin

            try:
                if cmd.is_jid_permitted_to_run(xmpp, user):
                    logger.info('User "%s" requested command "%s" (%s) [stream=%s] [reply=%s]',
                                user, body, cmd, stream, reply)
                else:
                    logger.warning('Unauthorized command "%s" (%s) from "%s"', body, cmd, user)
                    raise PermissionDenied

                if parse_parameters:  # Parse command parameters
                    args = cmd.get_args_from_msg_body(body)

                # Reply with function output
                response = fun(obj, msg, *args, **kwargs)

                if stream:
                    if reply:
                        _out = []

                        if response:
                            for line in response:
                                _out.append(line)
                                xmpp.msg_reply(msg, line, preserve_msg=True)
                        else:
                            xmpp.msg_reply(msg, '(no response)', preserve_msg=True)
                    else:
                        _out = response

                    out = '\n'.join(_out)
                else:
                    out = response
            except CommandError as e:
                out = str(e)
            except Exception as e:
                logger.exception(e)
                out = 'ERROR: Command failed due to internal programming error: %s' % e
            else:
                success = True
                logger.debug('Command output: "%s"', out)

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
