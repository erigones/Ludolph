"""
Ludolph: Monitoring Jabber Bot
Copyright (C) 2012-13 Erigones s. r. o.
This file is part of Ludolph.

See the LICENSE file for copying permission.
"""
from logging import getLogger

logger = getLogger(__name__)

COMMANDS = {}  # command : {name, module, doc}
USERS = []     # List of users
ADMINS = []    # List of admins


def command(f):
    """
    Decorator for registering available commands.
    """
    global COMMANDS
    global USERS

    def wrap(obj, msg, *args, **kwargs):
        user = obj._get_jid(msg).bare

        if not USERS or user in USERS:
            logger.info('User "%s" requested command "%s"', user, msg['body'])
            # Reply with output of function
            out = f(obj, msg, *args, **kwargs)
            logger.debug('Command output: "%s"', out)
            return msg.reply(out).send()
        else:
            logger.warning('Unauthorized command "%s" from "%s"', msg['body'], user)
            msg.reply('Permission denied').send()
            return None

    # Create command name - skip methods which start with underscore
    if f.__name__.startswith('_'):
        # Not a public command, but we will execute the method (private helper)
        return wrap
    else:
        name = f.__name__.replace('_', '-')

    # Check if command exists
    if name in COMMANDS.keys():
        logger.critical('Command "%s" from plugin "%s" overlaps with existing command from module "%s"',
                        name, f.__module__, COMMANDS[name]['module'])
        return None

    # Save module and method name
    COMMANDS[name] = {'name': f.__name__, 'module': f.__module__}

    # Save documentation
    if f.__doc__:
        COMMANDS[name]['doc'] = f.__doc__.strip()
    else:
        logger.error('Missing documentation for command "%s"', name)
        COMMANDS[name]['doc'] = ''

    return wrap


def parameter_required(count=1):
    """
    Decorator for required command parameters.
    """
    def parameter_required_decorator(f):
        def wrap(obj, msg, *args, **kwargs):
            #Try to get command parameter
            params = msg['body'].strip().split()[1:]
            if len(params) == count:
                params.extend(args)
                return f(obj, msg, *params, **kwargs)
            else:
                logger.warning('Missing parameter in command "%s" from user "%s"', msg['body'], obj._get_jid(msg).bare)
                msg.reply('Missing parameter').send()
                return None

        return wrap
    return parameter_required_decorator


def admin_required(f):
    """
    Decorator for admin only commands.
    """
    global ADMINS

    def wrap(obj, msg, *args, **kwargs):
        user = obj._get_jid(msg).bare

        if not ADMINS or user in ADMINS:
            return f(obj, msg, *args, **kwargs)
        else:
            logger.warning('Unauthorized command "%s" from user "%s"', msg['body'], user)
            msg.reply('Permission denied').send()
            return None

    return wrap
