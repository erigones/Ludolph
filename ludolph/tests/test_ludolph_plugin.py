"""
Ludolph: Monitoring Jabber Bot
Copyright (C) 2012-2017 Erigones, s. r. o.
This file is part of Ludolph.

See the LICENSE file for copying permission.
"""

import unittest
from ludolph.plugins.plugin import LudolphPlugin


class LudolphPluginTest(unittest.TestCase):

    plugin = None

    def setUp(self):
        # noinspection PyTypeChecker
        self.plugin = LudolphPlugin('xmpp', {'config': 'test'})

    def test_get_boolean_value(self):
        for i in (False, 'false', '0', 'no', 'off', 0, ''):
            self.assertEqual(self.plugin.get_boolean_value(i), False)

        for i in (True, 'true', '1', 'yes', 'on', 1, '_____'):
            self.assertEqual(self.plugin.get_boolean_value(i), True)

    def test_get_version(self):
        self.assertEqual(self.plugin.get_version(), '**Not implemented** by plugin author...')

if __name__ == '__main__':
    unittest.main()
