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

__all__ = ('LudolphDB', 'LudolphDBMixin')


class LudolphDB(Shelf):
    """
    Dictionary-like object used for saving/loading persistent data.
    """
    def __init__(self, filename, flag='c', protocol=None, writeback=False):
        self.filename = filename
        logger.info('Opening persistent DB file %s', filename)
        Shelf.__init__(self, dbm.open(filename, flag, mode=0o600), protocol, writeback)
        # logger.debug('Persistent DB file %s loaded following items: %s', filename, self)

    def __setitem__(self, key, value):
        logger.debug('Assigning item %r to persistent DB key "%s"', value, key)
        Shelf.__setitem__(self, key, value)

    def __delitem__(self, key):
        logger.debug('Removing key "%s" from persistent DB', key)
        Shelf.__delitem__(self, key)

    def sync(self):
        logger.info('Syncing persistent DB file %s', self.filename)
        Shelf.sync(self)
        # logger.debug('Persistent DB file %s synced with following items: %s', self.filename, self)

    def close(self):
        logger.info('Closing persistent DB file %s', self.filename)
        Shelf.close(self)
        # logger.debug('Persistent DB file %s closed with following items: %s', self.filename, self)


class LudolphDBMixin(object):
    """
    Interface for classes that want to use the LudolphDB object.
    """
    db = None

    def __init__(self, db=None):
        """Enable DB support if available"""
        if db is not None:
            self.db_enable(db, init=True)

    def _db_set_items(self):
        """Set/associate some object(s) with some DB key"""
        raise NotImplementedError

    def _db_load_items(self):
        """Load data from DB and update your object(s)"""
        raise NotImplementedError

    def db_enable(self, db, init=False):
        """Enable DB support in your object"""
        self.db = db

        if db is not None:
            if init:
                self._db_load_items()

            self._db_set_items()

    def db_disable(self):
        """Disable DB support in your object"""
        self.db = None
