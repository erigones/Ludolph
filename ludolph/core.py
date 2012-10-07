#!/usr/bin/python

import time
import logging
try:
    from jabberbot import JabberBot, botcmd
except ImportError:
    print >> sys.stderr, """
    You need to install jabberbot from http://thp.io/2007/python-jabberbot.
    On Debian-based systems, install the python-jabberbot package.
    """
    sys.exit(-1)

class LudolphCore(JabberBot):
    def __init__(self, config):
        self.config = config
        super(LudolphCore, self).__init__(config.get('ludolph','username'),
                config.get('ludolph','password'),
                config.get('ludolph','resource'))

        # create file handler
        chandler = logging.FileHandler(config.get('ludolph','log_file'))
        # create formatter
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        # add formatter to handler
        chandler.setFormatter(formatter)
        # add handler to logger
        self.log.addHandler(chandler)
        # set level to INFO
        self.log.setLevel(logging.INFO)

        self.message_queue = []
        self.thread_killed = False

    def idle_proc(self):
        if not len(self.message_queue):
            return

        # copy the message queue, then empty it
        messages = self.message_queue
        self.message_queue = []

        for message in messages:
            self.log.info('sending message to %s with text: "%s"' % (message[0], message[1]))
            self.send(message[0], message[1])

    def thread_proc(self):
        with open(PIPE, 'r') as fifo:
            while not self.thread_killed:
                line = fifo.readline().strip()
                if line:
                    data = line.split(';', 1)
                    if len(data) == 2:
                        self.message_queue.append(data)
                    else:
                        self.log.error('bad message format ("%s")' % (line))
                time.sleep(1)
                if self.thread_killed:
                    return

