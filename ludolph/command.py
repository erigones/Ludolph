"""
Ludolph: Monitoring Jabber Bot
Copyright (C) 2012-13 Erigones s.r.o.
This file is part of Ludolph.

See the LICENSE file for copying permission.
"""
from logging import getLogger

logger = getLogger(__name__)

COMMANDS = {}

def command(f):
    """
    Decorator for registering available commands.
    """
    if f.__doc__:
        COMMANDS[f.__name__] = f.__doc__.strip()
    else:
        logger.error('Missing documentation for command "%s"', f.__name__)
        COMMANDS[f.__name__] = ''

    def wrap(obj, msg, *args, **kwargs):
        if not obj.users or msg['from'].bare in obj.users:
            logger.info('User "%s" requested command "%s"' % (msg['from'],msg['body']))
            # Reply with output of function
            out = f(obj, msg, *args, **kwargs)
            logger.debug('Command output: "%s"', out)
            return msg.reply(out).send()
        else:
            logger.warning('Unauthorized command "%s" from "%s"' % (
                msg['body'], msg['from']))
            msg.reply('Permission denied').send()
            return None

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
                logger.warning('Missing parameter in command "%s" from user "%s"' % (
                    msg['body'], msg['from']))
                msg.reply('Missing parameter').send()
                return None

        return wrap
    return parameter_required_decorator

def admin_required(f):
    """
    Decorator for admin only commands.
    """
    def wrap(obj, msg, *args, **kwargs):
        if not obj.admins or msg['from'].bare in obj.admins:
            return f(obj, msg, *args, **kwargs)
        else:
            logger.warning('Unauthorized command "%s" from user "%s"' % (
                msg['body'], msg['from']))
            msg.reply('Permission denied').send()
            return None

    return wrap
