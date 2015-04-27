"""
Ludolph: Monitoring Jabber bot
Copyright (C) 2015 Erigones, s. r. o.
This file is part of Ludolph.

See the file LICENSE for copying permission.
"""
import logging
from shelve import Shelf

try:
    import anydbm as dbm
except ImportError:
    import dbm

logger = logging.getLogger(__name__)

__all__ = ('LudolphDB',)


class LudolphDB(Shelf):
    """
    Dictionary-like object used for saving/loading persistent data.
    """
    def __init__(self, filename, flag='c', protocol=None, writeback=True):
        self.filename = filename
        logger.info('Opening persistent DB file %s', filename)
        Shelf.__init__(self, dbm.open(filename, flag, mode=0o600), protocol, writeback)

    def __setitem__(self, key, value):
        logger.info('Assigning item %r to persistent DB key "%s"', value, key)
        Shelf.__setitem__(self, key, value)

    def __delitem__(self, key):
        logger.info('Removing key "%s" from persistent DB', key)
        Shelf.__delitem__(self, key)

    def sync(self):
        logger.info('Syncing persistent DB file %s', self.filename)
        Shelf.sync(self)

    def close(self):
        logger.info('Closing persistent DB file %s', self.filename)
        Shelf.close(self)
