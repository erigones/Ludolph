#!/usr/bin/python

import os
import sys
import threading
from core import LudolphCore
from jabberbot import botcmd
from ConfigParser import RawConfigParser

class Bot(LudolphCore):
    def __init__(self, config):
        super(Bot, self).__init__(config)

    @botcmd
    def uptime(self, mess, args):
        """
        Display system uptime
        """
        return plugins.uptime()

    @botcmd
    def set_status(self, mess, args):
        """
        Set status to anything you send as parameter
        """
        return plugins.set_status(self, args)

    @botcmd
    def about(self, mess, args):
        """
        Information about bot (available params: version, licence)
        """
        if args == 'version':
            return plugins.version()
        elif args == 'licence':
            return plugins.licence()
        else:
            return plugins.about()

def start():
    config = RawConfigParser()
    path = os.path.dirname(os.path.abspath(__file__))
    try:
        config.readfp(open(path +'/config.cfg'))
    except IOError:
        print >> sys.stderr, """
        You need to create a config file. You can rename config.example.cfg
        and update required variables. See example file for more details.
        File is located: """+ path +"\n"
        sys.exit(-1)

    os.mkfifo(config.get('ludolph','pipe_file'), 0600)
    try:
        ludolph_bot = Bot(config)
        th = threading.Thread(target = ludolph_bot.thread_proc)
        #set thread as daemon so it is terminated once main program ends
        th.daemon = True
        ludolph_bot.serve_forever(connect_callback = lambda: th.start())
        ludolph_bot.thread_killed = True
    finally:
        os.remove(config.get('ludolph','pipe_file'))

if __name__ == '__main__':
    start()
