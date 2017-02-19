"""
Ludolph: Monitoring Jabber Bot
Copyright (C) 2012-2017 Erigones, s. r. o.
This file is part of Ludolph.

See the LICENSE file for copying permission.
"""

import unittest
from ludolph.tests.fake_bot import FakeLudolphBot
from ludolph.plugins.base import Base


class LudolphCommandsTest(unittest.TestCase):

    base = None

    def setUp(self):
        xmpp = FakeLudolphBot()  # Reference to LudolphBot object
        config = {
            'dummy': 'test'
        }
        # noinspection PyTypeChecker
        self.base = Base(xmpp, config)

    def test__roster_list(self):
        roster = '\n'.join(['%s\t%s' % (i, self.base.xmpp.client_roster[i]['subscription'])
                            for i in self.base.xmpp.client_roster])
        self.assertEqual(self.base._roster_list(), roster)


if __name__ == '__main__':
    unittest.main()
