"""
Ludolph: Monitoring Jabber Bot
Copyright (C) 2012-13 Erigones s.r.o.
This file is part of Ludolph.

See the LICENSE file for copying permission.
"""

import os
import sys
import ssl
import time
import logging
import subprocess

from sleekxmpp import ClientXMPP
from __init__ import __doc__ as ABOUT
from __init__ import __version__ as VERSION

# In order to make sure that Unicode is handled properly
# in Python 2.x, reset the default encoding.
if sys.version_info < (3, 0):
    from ConfigParser import RawConfigParser
else:
    from configparser import RawConfigParser

logger = logging.getLogger(__name__)

COMMANDS = {}

def command(f):
    """
    Decorator for registering available commands.
    """
    COMMANDS[f.__name__] = f.__doc__.strip()

    def wrap(obj, msg, *args, **kwargs):
        if not obj.users or msg['from'].bare in obj.users:
            logger.info('User "%s" requested command "%s"' % (msg['from'],msg['body']))
            return f(obj, msg, *args, **kwargs)
        else:
            logger.warning('Unauthorized command "%s" from "%s"' % (
                msg['body'], msg['from']))
            msg.reply('Permission denied').send()

        return f(obj, msg, *args, **kwargs)

    return wrap

def parameter_required(count=1):
    """
    Decorator for required command parameters.
    """
    def parameter_required_decorator(f):
        def wrap(obj, msg, *args, **kwargs):
            #Try to get command parameter
            params = msg['body'].strip().split()[1:]
            if len(params) != count:
                logger.warning('Missing parameter in command "%s" from user "%s"' % (
                    msg['body'], msg['from']))
                msg.reply('Missing parameter').send()
            else:
                params.extend(args)
                return f(obj, msg, *params, **kwargs)
        return wrap
    return parameter_required_decorator

def admin_required(f):
    """
    Decorator for admin only commands.
    """
    def wrap(obj, msg, *args, **kwargs):
        if not obj.admins or msg['from'].bare in obj.admins:
            return f(obj, msg, *args, **kwargs)
        else:
            logger.warning('Unauthorized command "%s" from user "%s"' % (
                msg['body'], msg['from']))
            msg.reply('Permission denied').send()

    return wrap

class LudolphBot(ClientXMPP):
    """
    Ludolph bot.
    """
    commands = COMMANDS
    users = []
    admins = []

    def __init__(self, config):
        # Initialize the SleeXMPP client
        ClientXMPP.__init__(self,
                config.get('xmpp','username'),
                config.get('xmpp','password'))

        # If you are working with an OpenFire server, you will
        # need to use a different SSL version:
        if config.has_option('xmpp', 'sslv3') and \
            config.getboolean('xmpp', 'sslv3'):
                self.ssl_version = ssl.PROTOCOL_SSLv3

        # Auto-authorize is enabled by default. User subscriptions are
        # controlled by self._handle_new_subscription
        self.auto_authorize = True

        # Rest of the configuration
        self.config = config
        self.pipe_file = config.get('global','pipe_file')

        # Users
        if config.has_option('xmpp', 'users'):
            for i in config.get('xmpp', 'users').strip().split(','):
                i = i.strip()
                if i:
                    self.users.append(i)

        # Admins
        if config.has_option('xmpp', 'admins'):
            for i in config.get('xmpp', 'admins').strip().split(','):
                i = i.strip()
                if i:
                    self.admins.append(i)

        # Admins vs. users
        if self.admins and self.users:
            for i in self.admins:
                if i not in self.users:
                    logger.error('Admin user %s is not specified in users. '
                            'This may lead to unexpected behaviour. ', i)

        # Register event handlers
        self.add_event_handler('session_start', self.session_start)
        self.add_event_handler('message', self.message)

        # Start the monitoring thread for reading the pipe file
        self._start_thread('mon_thread', self.mon_thread)

    def _handle_new_subscription(self, pres):
        """
        xmpp.auto_authorize is True by default, which is fine. But we want to
        restrict this to users only (if set). We do this by overriding the
        automatic subscription mechanism.
        """
        user = pres['from']

        if not self.users or user in self.users:
            logger.info('Allowing user "%s" to auto subscribe', user)
            return super(LudolphBot, self)._handle_new_subscription(pres)
        else:
            logger.warning('User "%s" is not allowed to susbscribe', user)

    def session_start(self, event):
        """
        Process the session_start event.
        """
        self.send_presence()
        self.get_roster()
        self.roster_cleanup()
        logger.info('Registered commands: %s', ', '.join(self.commands))

    def roster_cleanup(self):
        """
        Remove roster items with none subscription.
        """
        roster = self.client_roster
        logger.info('Current auto_authorize: %s', self.auto_authorize)
        logger.info('Current users: %s', ', '.join(self.users))
        logger.info('Current admins: %s', ', '.join(self.admins))
        logger.info('Current roster: %s', ', '.join(roster.keys()))

        # Remove users with none subscription from roster
        # Also remove users that are not in users setting (if set)
        for i in roster.keys():
            if roster[i]['subscription'] == 'none' or \
                (self.users and i not in self.users):
                    logger.warning('Roster item: %s (%s) - removing!' % (
                        i, roster[i]['subscription']))
                    self.send_presence(pto=i, ptype='unsubscribe')
                    self.del_roster_item(i)
            else:
                logger.info('Roster item: %s (%s) - ok' % (
                    i, roster[i]['subscription']))

    def available_commands(self):
        """
        List of all available bot commands.
        """
        return self.commands.keys()

    def message(self, msg):
        """
        Incoming message handler.
        """
        if msg['type'] in ('chat', 'normal'):
            # Seek received text in available commands
            cmd = msg['body'].split()[0].strip()
            if cmd in self.available_commands():
                # Run command
                f = getattr(self, cmd)
                return f(msg)
            else:
                # Send message that command was not understod and what to do
                msg.reply('Sorry, I don\'t understand "%s"\n'
                        'Please type "help" for more info' % msg['body']).send()

    def mon_thread(self):
        """
        Processing input from the monitoring pipe file.
        """
        with os.fdopen(os.open(self.pipe_file, os.O_RDONLY|os.O_NONBLOCK)) as fifo:
            logger.info('Processing input from monitoring pipe file')
            while not self.stop.is_set():
                line = fifo.readline().strip()
                if line:
                    data = line.split(';', 1)
                    if len(data) == 2:
                        logger.info('Sending monitoring message to %s', data[0])
                        logger.debug('\twith body: "%s"', data[1])
                        self.send_message(mto=data[0], mbody=data[1],
                                mtype='normal')
                    else:
                        logger.warning('Bad message format ("%s")', line)

                time.sleep(1)

                if self.stop.is_set():
                    self._end_thread('mon_thread', early=True)
                    return

    @command
    def help(self, msg):
        """
        Show this help.
        """
        out = ['List of available Ludolph commands:']

        for cmd, info in self.commands.iteritems():
            # First line of __doc__
            desc = info.split('\n')[0]
            # Lowercase first char and remove trailing dot
            desc = desc[0].lower() + desc[1:].rstrip('.')
            # Append line of command + description
            out.append('\t* %s - %s' % (cmd, desc))

        msg.reply('\n'.join(out)).send()

    @command
    def version(self, msg):
        """
        Display Ludolph version.
        """
        msg.reply('Version: '+ VERSION).send()

    @command
    def about(self, msg):
        """
        Details about this project.
        """
        msg.reply(ABOUT.strip()).send()

    @admin_required
    @command
    def roster_list(self, msg):
        """
        List of users on Ludolph's roster (admin only).
        """
        roster = self.client_roster
        out = ['| JID | subscription |']

        for i in roster.keys():
            out.append('| %s | %s |' % (str(i), roster[i]['subscription']))

        msg.reply('\n'.join(out)).send()

    @admin_required
    @parameter_required(1)
    @command
    def roster_remove(self, msg, user):
        """
        Remove user from Ludolph's roster (admin only).
        """
        if user in self.client_roster.keys():
            self.send_presence(pto=user, ptype='unsubscribe')
            self.del_roster_item(user)
            msg.reply('User '+ user +' removed from roster').send()
        else:
            msg.reply('User '+ user +' cannot be removed from roster').send()

    @command
    def uptime(self, msg):
        """
        Show server uptime.
        """
        cmd = subprocess.Popen(['uptime'], stdout=subprocess.PIPE)
        msg.reply(cmd.communicate()[0]).send()


def main():
    """
    Start the daemon.
    """
    cfg = 'ludolph.cfg'
    cfg_fp = None
    cfg_lo = ((os.path.expanduser('~'), '.'+ cfg),
            (sys.prefix, 'etc', cfg), ('/etc', cfg))
    config = RawConfigParser()

    # Try to read config file from ~/.ludolph.cfg or /etc/ludolph.cfg
    for i in cfg_lo:
            try:
                cfg_fp = open(os.path.join(*i))
            except IOError:
                continue
            else:
                break

    if cfg_fp:
        config.readfp(cfg_fp)
    else:
        print >> sys.stderr, """Ludolph can't start!\n
You need to create a config file in one this locations: \n%s\n
You can rename ludolph.cfg.example and update the required variables.
The example file is located in: %s\n""" % (
        '\n'.join([os.path.join(*i) for i in cfg_lo]),
        os.path.dirname(os.path.abspath(__file__)))
        sys.exit(1)

    # Setup logging
    logging.basicConfig(filename=config.get('global','logfile'),
                        level=config.get('global','loglevel'),
                        format='%(asctime)s %(levelname)-8s %(message)s')
    # All exceptions will be logged
    def log_except_hook(*exc_info):
        logger.critical('Unhandled exception!', exc_info=exc_info)
    sys.excepthook = log_except_hook

    # Default configuration
    pipe_file = config.get('global','pipe_file')
    pipe_mode = '0600'
    use_tls = True
    use_ssl = False
    address = []

    # Starting
    logger.info('Starting Ludolph %s', VERSION)
    logger.info('Loaded configuration from %s', cfg_fp.name)

    # XMPP connection settings
    if config.has_option('xmpp', 'host'):
        address = [config.get('xmpp', 'host'), '5222']
        if config.has_option('xmpp', 'port'):
            address[1] = config.get('xmpp', 'port')
        logger.info('Connecting to jabber server %s', ':'.join(address))
    else:
        logger.info('Using DNS SRV lookup to find jabber server')

    if config.has_option('xmpp', 'tls'):
        use_tls = config.getboolean('xmpp', 'tls')

    if config.has_option('xmpp', 'ssl'):
        use_ssl = config.getboolean('xmpp', 'ssl')

    # Create pipe file with desired permissions
    if config.has_option('global', 'pipe_mode'):
        pipe_mode = config.get('global', 'pipe_mode')

    logger.info('Creating pipe file %s', pipe_file)
    os.mkfifo(pipe_file, int(pipe_mode, 8))

    # Here we go
    try:
        xmpp = LudolphBot(config)
        if xmpp.connect(tuple(address), use_tls=use_tls, use_ssl=use_ssl):
            xmpp.process(block=True)
        else:
            logger.error('Ludolph is unable to connect to jabber server')
            sys.exit(2)
    finally:
        # Cleanup
        logger.info('Removing pipe file %s', pipe_file)
        os.remove(pipe_file)


if __name__ == '__main__':
    main()
