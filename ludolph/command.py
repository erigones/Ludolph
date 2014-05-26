"""
Ludolph: Monitoring Jabber Bot
Copyright (C) 2012-2014 Erigones s. r. o.
This file is part of Ludolph.

See the LICENSE file for copying permission.
"""
from logging import getLogger

logger = getLogger(__name__)

COMMANDS = {}  # command : (name, module, doc)
USERS = set()  # List of users
ADMINS = set()  # List of admins

__all__ = ('command', 'parameter_required', 'admin_required')


def command(fun):
    """
    Decorator for registering available commands.
    """
    global COMMANDS
    global USERS

    def wrap(obj, msg, *args, **kwargs):
        user = obj.xmpp.get_jid(msg)
        cmd = '%s.%s' % (fun.__module__, fun.__name__)

        if not USERS or user in USERS:
            logger.info('User "%s" requested command "%s" (%s)', user, msg['body'], cmd)
            # Parse optional parameters
            if fun.__defaults__:
                required_pos = len(args) + 1
                optional_end = required_pos + len(fun.__defaults__)
                optional_args = msg['body'].strip().split()[required_pos:optional_end]
                args += tuple(optional_args)

            # Reply with function output
            out = fun(obj, msg, *args, **kwargs)
            logger.debug('Command output: "%s"', out)
            obj.xmpp.msg_reply(msg, out)
            return True
        else:
            logger.warning('Unauthorized command "%s" (%s) from "%s"', msg['body'], cmd, user)
            obj.xmpp.msg_reply(msg, 'ERROR: Permission denied')
            return None

    # Create command name - skip methods which start with underscore
    if fun.__name__.startswith('_'):
        # Not a public command, but we will execute the method (private helper)
        return wrap
    else:
        name = fun.__name__.replace('_', '-')

    # Check if command exists
    if name in COMMANDS:
        logger.critical('Command "%s" from plugin "%s" overlaps with existing command from module "%s"',
                        name, fun.__module__, COMMANDS[name][1])
        return None

    # Save documentation
    if fun.__doc__:
        doc = fun.__doc__.strip()
    else:
        logger.warning('Missing documentation for command "%s"', name)
        doc = ''

    # Save module and method name
    logger.debug('Registering command "%s" from plugin "%s"', name, fun.__module__)
    COMMANDS[name] = (fun.__name__, fun.__module__, doc)

    return wrap


def parameter_required(count):
    """
    Decorator for required command parameters.
    """
    def parameter_required_decorator(fun):
        def wrap(obj, msg, *args, **kwargs):
            #Try to get command parameter
            params = msg['body'].strip().split()[1:]

            if len(params) < count:
                user = obj.xmpp.get_jid(msg)
                logger.warning('Missing parameter in command "%s" from user "%s"', msg['body'], user)
                obj.xmpp.msg_reply(msg, 'ERROR: Missing parameter')
                return None
            else:
                params.extend(args)
                return fun(obj, msg, *params, **kwargs)

        return wrap
    return parameter_required_decorator


def admin_required(fun):
    """
    Decorator for admin only commands.
    """
    global ADMINS

    def wrap(obj, msg, *args, **kwargs):
        user = obj.xmpp.get_jid(msg)

        if not ADMINS or user in ADMINS:
            return fun(obj, msg, *args, **kwargs)
        else:
            logger.warning('Unauthorized command "%s" from user "%s"', msg['body'], user)
            obj.xmpp.msg_reply(msg, 'ERROR: Permission denied')
            return None

    return wrap
