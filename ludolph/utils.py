"""
Ludolph: Monitoring Jabber Bot
Copyright (C) 2014-2015 Erigones, s. r. o.
This file is part of Ludolph.

See the LICENSE file for copying permission.
"""
import logging

LOG_LEVELS = frozenset(['DEBUG', 'INFO', 'WARN', 'WARNING', 'ERROR', 'FATAL', 'CRITICAL'])


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
