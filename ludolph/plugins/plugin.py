"""
Ludolph: Monitoring Jabber bot
Copyright (C) 2012-2014 Erigones s. r. o.
This file is part of Ludolph.

See the file LICENSE for copying permission.
"""


class LudolphPlugin(object):
    """
    Ludolph plugin base class.
    """
    xmpp = None  # Reference to LudolphBot object
    config = None  # Plugin configuration as list of (name, value) tuples

    # noinspection PyUnusedLocal
    def __init__(self, xmpp, config, reinit=False, **kwargs):
        self.xmpp = xmpp
        self.config = dict(config)
