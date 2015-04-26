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

__all__ = ('command', 'parameter_required', 'admin_required')

logger = getLogger(__name__)


class CommandError(Exception):
    pass


class Command(namedtuple('Command', ('cmd', 'fun', 'name', 'module', 'doc'))):
    """
    Ludolph command wrapper.
    """
    def get_fun(self, bot):
        """Get command bound method from plugin"""
        return getattr(bot.plugins[self.module], self.name)


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
        return ['%s [%s]' % (name, cmd.module.split('.')[-1]) for name, cmd in self.items()]

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


COMMANDS = Commands()  # command : (name, module, doc)
USERS = set()  # List of users
ADMINS = set()  # List of admins


def command(func=None, stream_output=False, reply_output=True):
    """
    Decorator for registering available commands.
    """
    global COMMANDS
    global USERS

    def command_decorator(fun):
        @wraps(fun)
        def wrap(obj, msg, *args, **kwargs):
            cmd = '%s.%s' % (fun.__module__, fun.__name__)
            user = obj.xmpp.get_jid(msg)
            success = False
            reply = msg.get_reply_output(default=reply_output, set_default=True)  # Used for scheduled "at" jobs
            stream = msg.get_stream_output(default=stream_output, set_default=True)  # Not used

            if not USERS or user in USERS:
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
                                obj.xmpp.msg_reply(msg, line, preserve_msg=True)
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

                obj.xmpp.msg_reply(msg, out)

            return out

        # Create command name - skip methods which start with underscore
        if fun.__name__.startswith('_'):
            # Not a public command, but we will execute the method (private helper)
            return wrap
        else:
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
        fun.admin_required = False
        COMMANDS[name] = Command(name, fun, fun.__name__, fun.__module__, doc)

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
    Decorator for admin only commands.
    """
    global ADMINS

    fun.admin_required = True

    @wraps(fun)
    def wrap(obj, msg, *args, **kwargs):
        user = obj.xmpp.get_jid(msg)

        if not ADMINS or user in ADMINS:
            return fun(obj, msg, *args, **kwargs)
        else:
            logger.warning('Unauthorized command "%s" from user "%s"', msg['body'], user)
            obj.xmpp.msg_reply(msg, 'ERROR: Permission denied')
            return None

    return wrap
