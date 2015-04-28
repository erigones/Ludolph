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
    xmpp = None  # Reference to LudolphBot object
    config = None  # Plugin configuration as list of (name, value) tuples
    persistent_attrs = ()  # Set of object's attributes that will be saved/loaded during bot's shutdown/start events.

    # noinspection PyUnusedLocal
    def __init__(self, xmpp, config, reinit=False, **kwargs):
        self.xmpp = xmpp
        self.config = dict(config)

    def __repr__(self):
        return '<LudolphPlugin: %s.%s>' % (self.__class__.__module__, self.__class__.__name__)

    def __getstate__(self):
        # FIXME: Switch to dict comprehension after dropping support for Python 2.6
        return dict((i, self.__dict__[i]) for i in self.persistent_attrs if i in self.__dict__)

    def __setstate__(self, state):
        for i in state:
            if i in self.persistent_attrs:
                self.__dict__[i] = state[i]
