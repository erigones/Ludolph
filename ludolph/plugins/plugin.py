"""
Ludolph: Monitoring Jabber bot
Copyright (C) 2012-2015 Erigones, s. r. o.
This file is part of Ludolph.

See the file LICENSE for copying permission.
"""


class LudolphPlugin(object):
    """
    Ludolph plugin base class.
    """
    __version__ = None
    persistent_attrs = ()  # Set of object's attributes that will be saved/loaded during bot's shutdown/start events.

    # noinspection PyUnusedLocal
    def __init__(self, xmpp, config, reinit=False, **kwargs):
        self.xmpp = xmpp  # Reference to LudolphBot object
        self.config = dict(config)  # Plugin configuration as list of (name, value) tuples
        self._reloaded = reinit

    def __repr__(self):
        return '<LudolphPlugin: %s.%s>' % (self.__class__.__module__, self.__class__.__name__)

    # noinspection PyMethodMayBeStatic
    def __post_init__(self):
        """Run after ludolph bot instance is up and running"""
        pass

    # noinspection PyMethodMayBeStatic
    def __destroy__(self):
        """Run before ludolph bot reload or shutdown"""
        pass

    def __getstate__(self):
        # FIXME: Switch to dict comprehension after dropping support for Python 2.6
        return dict((i, self.__dict__[i]) for i in self.persistent_attrs if i in self.__dict__)

    def __setstate__(self, state):
        for i in state:
            if i in self.persistent_attrs:
                self.__dict__[i] = state[i]

    def _db_save(self):
        """Save persistent attributes now"""
        if self.xmpp.db is not None:
            # noinspection PyProtectedMember
            self.xmpp._db_set_item(self.__class__.__module__, self)

    def _db_load(self):
        """Load persistent attributes from DB"""
        if self.xmpp.db is not None:
            # noinspection PyProtectedMember
            self.xmpp._db_load_item(self.__class__.__module__, self)

    @classmethod
    def get_version(cls):
        """Used by the version command"""
        if cls.__version__ is None:
            return '**Not implemented** by plugin author...'
        else:
            return '**%s**' % cls.__version__
