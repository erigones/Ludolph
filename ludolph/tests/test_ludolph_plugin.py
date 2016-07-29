import unittest
from ludolph.plugins.plugin import LudolphPlugin


class LudolphPluginTest(unittest.TestCase):

    def setUp(self):
        pass

    def test_get_boolean_value(self):
        plugin = LudolphPlugin('xmpp', {'config': 'test'})
        self.assertEqual(plugin.get_boolean_value(False), False)
        self.assertEqual(plugin.get_boolean_value('false'), False)
        self.assertEqual(plugin.get_boolean_value('0'), False)
        self.assertEqual(plugin.get_boolean_value('no'), False)
        self.assertEqual(plugin.get_boolean_value('off'), False)
        self.assertEqual(plugin.get_boolean_value(0), False)
        self.assertEqual(plugin.get_boolean_value(''), False)
        self.assertEqual(plugin.get_boolean_value(True), True)
        self.assertEqual(plugin.get_boolean_value('true'), True)
        self.assertEqual(plugin.get_boolean_value('1'), True)
        self.assertEqual(plugin.get_boolean_value('yes'), True)
        self.assertEqual(plugin.get_boolean_value('on'), True)
        self.assertEqual(plugin.get_boolean_value(1), True)
        self.assertEqual(plugin.get_boolean_value(' '), True)


if __name__ == '__main__':
    unittest.main()
