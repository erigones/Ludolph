"""
Ludolph: Monitoring Jabber bot
Copyright (C) 2012-13 Erigones s. r. o.
This file is part of Ludolph.

See the file LICENSE for copying permission.
"""


class LudolphPlugin(object):
    """
    Ludolph plugin base class.
    """
    xmpp = None  # Reference to LudolphBot object

    def __init__(self, config, *args, **kwargs):
        pass  # Implement plugin initialization here

    def reload(self, config):
        pass  # Implement plugin reloading here
