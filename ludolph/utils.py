"""
Ludolph: Monitoring Jabber Bot
Copyright (C) 2014-2015 Erigones, s. r. o.
This file is part of Ludolph.

See the LICENSE file for copying permission.
"""
import logging
import os


def parse_loglevel(name):
    """Parse log level name and return log level integer value"""
    name = name.upper()

    if name in ('DEBUG', 'INFO', 'WARN', 'WARNING', 'ERROR', 'FATAL', 'CRITICAL'):
        return getattr(logging, name, logging.INFO)

    return logging.INFO


def get_avatar_dir_list(config):
    """ Get list of directories where are avatars stored """
    avatar_dir = config.get('avatar_dir', None)

    if avatar_dir:
        return ((avatar_dir,), (os.path.dirname(os.path.abspath(__file__)), 'avatars'))
    else:
        return ((os.path.dirname(os.path.abspath(__file__)), 'avatars'),)