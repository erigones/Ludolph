"""
Ludolph: Monitoring Jabber Bot
Copyright (C) 2014 Erigones s. r. o.
This file is part of Ludolph.

See the LICENSE file for copying permission.
"""
import logging


def parse_loglevel(name):
    """Parse log level name and return log level integer value"""
    name = name.upper()

    if name in ('DEBUG', 'INFO', 'WARN', 'WARNING', 'ERROR', 'FATAL', 'CRITICAL'):
        return getattr(logging, name, logging.INFO)

    return logging.INFO