"""
Ludolph: Monitoring Jabber Bot
Copyright (C) 2014-2015 Erigones, s. r. o.
This file is part of Ludolph.

See the LICENSE file for copying permission.
"""
import logging
from functools import wraps

LOG_LEVELS = frozenset(['DEBUG', 'INFO', 'WARN', 'WARNING', 'ERROR', 'FATAL', 'CRITICAL'])

logger = logging.getLogger(__name__)


def parse_loglevel(name):
    """Parse log level name and return log level integer value"""
    name = name.upper()

    if name in LOG_LEVELS:
        return getattr(logging, name, logging.INFO)

    return logging.INFO


def pluralize(count, singular, plural):
    """Return singular or plural depending on count"""
    if count == 1:
        return singular
    return plural


def catch_exception(fun):
    """
    Used as decorator to catch all exceptions and log them without breaking the inner function.
    """
    @wraps(fun)
    def wrap(*args, **kwargs):
        try:
            return fun(*args, **kwargs)
        except Exception as e:
            logger.exception(e)
            logger.error('Got exception when running %s(%s, %s): %s.', fun.__name__, args, kwargs, e)
    return wrap
