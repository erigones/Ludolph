"""
Ludolph: Monitoring Jabber Bot
Copyright (C) 2012-2017 Erigones, s. r. o.
This file is part of Ludolph.

See the LICENSE file for copying permission.
"""


class FakeLudolphBot(object):
    """
    Fake Ludolph bot, for testing purposes.

    Minimal class needs to be updated so it can be used by test for dummy inputs/outputs
    """
    client_roster = None

    def __init__(self):
        self.update_roster(('ludolph@test.com', 'friend1@test.com', 'friend2@test.com'))

    def update_roster(self, new_roster):
        self.client_roster = {}

        for jid in new_roster:
            self.client_roster[jid] = {
                'subscription': 'both'
            }
