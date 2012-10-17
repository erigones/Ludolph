import sys
import os
import logging

from sleekxmpp import ClientXMPP
from sleekxmpp.exceptions import IqError, IqTimeout

# In order to make sure that Unicode is handled properly
# in Python 2.x, reset the default encoding.
if sys.version_info < (3, 0):
    from ConfigParser import RawConfigParser
else:
    from configparser import RawConfigParser


class EchoBot(ClientXMPP):

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
            if msg == 'help':
                msg.reply("this is help text").send()
            else:
                msg.reply("Thanks for sending\n%(body)s" % msg).send()


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

    xmpp = EchoBot(config)
    xmpp.connect()
    xmpp.process(block=True)

if __name__ == '__main__':
    start()
