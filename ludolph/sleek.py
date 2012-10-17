import sys
import os
import logging

from sleekxmpp import ClientXMPP
from sleekxmpp.exceptions import IqError, IqTimeout
from version import __version__
# In order to make sure that Unicode is handled properly
# in Python 2.x, reset the default encoding.
if sys.version_info < (3, 0):
    from ConfigParser import RawConfigParser
else:
    from configparser import RawConfigParser


class LudolphBot(ClientXMPP):

    def __init__(self, config):
        ClientXMPP.__init__(self,
                config.get('ludolph','username'),
                config.get('ludolph','password'))

        self.add_event_handler("session_start", self.session_start)
        self.add_event_handler("message", self.message)

        # If you wanted more functionality, here's how to register plugins:
        # self.register_plugin('xep_0030') # Service Discovery
        # self.register_plugin('xep_0199') # XMPP Ping

        # Here's how to access plugins once you've registered them:
        # self['xep_0030'].add_feature('echo_demo')

        # If you are working with an OpenFire server, you will
        # need to use a different SSL version:
        # import ssl
        # self.ssl_version = ssl.PROTOCOL_SSLv3

    def session_start(self, event):
        self.send_presence()
        self.get_roster()

        # Most get_*/set_* methods from plugins use Iq stanzas, which
        # can generate IqError and IqTimeout exceptions
        #
        # try:
        #     self.get_roster()
        # except IqError as err:
        #     logging.error('There was an error getting the roster')
        #     logging.error(err.iq['error']['condition'])
        #     self.disconnect()
        # except IqTimeout:
        #     logging.error('Server is taking too long to respond')
        #     self.disconnect()

    def message(self, msg):
        if msg['type'] in ('chat', 'normal'):
            # Seek received text in available commands
            if msg['body'] in self.available_commands():
                # transform string into executable function
                function = getattr(self, msg['body'])
                function(msg)
            else:
                # Send message that command was not understod and what to do
                self.send_message(mto=msg['from'],
                                mbody="I dont understand %(body)s." % msg,
                                mtype='chat')
                self.send_message(mto=msg['from'],
                                mbody="Please type help for more info",
                                mtype='chat')

    def available_commands(self):
        return {'help' : 'disply available commands',
                'version' : 'show current version',
                'about' : 'dispaly more information about Ludolph'
                }
        # List of all available commands for bot

    def help(self, msg):
        self.send_message(mto=msg['from'],
                        mbody='List of known commands:',
                        mtype='chat')
        all_commands = self.available_commands()
        for command in all_commands:
            self.send_message(mto=msg['from'],
                    mbody=str(command) +" - "+ str(all_commands[command]),
                    mtype='chat')
        # Function to send out available commands if called

    def version(self, msg):
        msg.reply('Version: '+ __version__).send()
        # pely with a Ludolph version to user

    def about(self, msg):
        msg.reply("""
            Ludolph - Monitoring Jabber bot
            Version: """+ __version__ +"""
            Homepage: https://github.com/ricco386/Ludolph
            Copyright (C) 2012 Richard Kellner & Daniel Kontsek
            This program comes with ABSOLUTELY NO WARRANTY. For details type
            'about'.
            This is free software, and you are welcome to redistribute it under
            certain conditions.""").send()
        # details about what is this project aobut

def start():
    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)-8s %(message)s')

    config = RawConfigParser()
    path = os.path.dirname(os.path.abspath(__file__))

    try:
        config.readfp(open(path +'/config.cfg'))
    except IOError:
        print >> sys.stderr, """
        You need to create a config file. You can rename config.example.cfg
        and update required variables. See example file for more
        details.
        File is located: """+ path +"\n"
        sys.exit(-1)

    xmpp = LudolphBot(config)
    xmpp.connect()
    xmpp.process(block=True)

if __name__ == '__main__':
    start()
