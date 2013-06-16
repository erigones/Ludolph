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
import signal
import logging
import subprocess
from sleekxmpp import ClientXMPP
from tabulate import tabulate

# In order to make sure that Unicode is handled properly
# in Python 2.x, reset the default encoding.
if sys.version_info < (3, 0):
    from ConfigParser import RawConfigParser
else:
    from configparser import RawConfigParser

from ludolph.command import ( COMMAND_MAP, COMMANDS, USERS, ADMINS,
        command, parameter_required, admin_required )
from ludolph.__init__ import __doc__ as ABOUT
from ludolph.__init__ import __version__ as VERSION

LOGFORMAT = '%(asctime)s %(levelname)-8s %(name)s: %(message)s'
TABLEFMT = 'simple'

logger = logging.getLogger(__name__)

class LudolphBot(ClientXMPP):
    """
    Ludolph bot.
    """
    command_map = COMMAND_MAP
    commands = COMMANDS
    users = USERS
    admins = ADMINS
    plugins = None

    def __init__(self, config, plugins=None, *args, **kwargs):
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

        # Initialize plugins
        self.plugins = {'__main__': self, 'ludolph.bot': self}
        if plugins:
            for plugin, cls in plugins.items():
                logger.info('Initializing plugin %s', plugin)
                self.plugins[plugin] = cls(config)

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
        logger.info('Registered commands: %s', ', '.join(self.available_commands()))

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
                # Find and run command
                f = getattr(self.plugins[self.command_map[cmd]], cmd)
                return f(msg)
            else:
                # Send message that command was not understod and what to do
                msg.reply('Sorry, I don\'t understand "%s"\n'
                        'Please type "help" for more info' % msg['body']).send()

    def shutdown(self, signalnum, handler):
        """
        Shutdown signal handler.
        """
        logger.info('Requested shutdown (%s)', signalnum)

        return self.abort()

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
        # Global help or command help?
        cmdline = msg['body'].strip().split()
        if len(cmdline) > 1 and cmdline[1] in self.available_commands():
            out = ['* ' + cmdline[1], '', self.commands[cmdline[1]]]
        else:
            out = ['List of available Ludolph commands:']

            for cmd, info in self.commands.items():
                try:
                    # First line of __doc__
                    desc = info.split('\n')[0]
                    # Lowercase first char and remove trailing dot
                    desc = desc[0].lower() + desc[1:].rstrip('.')
                except IndexError:
                    desc = ''
                # Append line of command + description
                out.append('\t* %s - %s' % (cmd, desc))

        return '\n'.join(out)

    @command
    def version(self, msg):
        """
        Display Ludolph version.
        """
        return 'Version: '+ VERSION

    @command
    def about(self, msg):
        """
        Details about this project.
        """
        return ABOUT.strip()

    @admin_required
    @command
    def roster_list(self, msg):
        """
        List of users on Ludolph's roster (admin only).
        """
        roster = self.client_roster
        out = []

        for i in roster.keys():
            out.append((str(i), roster[i]['subscription'],))

        return str(tabulate(out, headers=['JID', 'subscription'], tablefmt=TABLEFMT))

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
            return 'User '+ user +' removed from roster'
        else:
            return 'User '+ user +' cannot be removed from roster'

    @command
    def uptime(self, msg):
        """
        Show server uptime.
        """
        cmd = subprocess.Popen(['uptime'], stdout=subprocess.PIPE)

        return cmd.communicate()[0]


def daemonize():
    """
    http://code.activestate.com/recipes/278731-creating-a-daemon-the-python-way/
    http://www.jejik.com/articles/2007/02/a_simple_unix_linux_daemon_in_python/
    """
    try:
        pid = os.fork() # Fork #1
        if pid > 0:
            sys.exit(0) # Exit first parent
    except OSError as e:
        sys.stderr.write('Fork #1 failed: %d (%s)\n' % (e.errno, e.strerror))
        sys.exit(1)

    # The first child. Decouple from parent environment
    # Become session leader of this new session.
    # Also be guaranteed not to have a controlling terminal
    os.chdir('/')
    os.setsid()
    os.umask(0)

    try:
        pid = os.fork() # Fork #2
        if pid > 0:
            sys.exit(0) # Exit from second parent
    except OSError as e:
        sys.stderr.write('Fork #2 failed: %d (%s)\n' % (e.errno, e.strerror))
        sys.exit(1)

    # Close all open file descriptors
    import resource # Resource usage information
    maxfd = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
    if (maxfd == resource.RLIM_INFINITY):
        maxfd = 1024

    # Iterate through and close all file descriptors
    for fd in range(0, maxfd):
        try:
            os.close(fd)
        except OSError: # ERROR, fd wasn't open (ignored)
            pass

    # Redirect standard file descriptors to /dev/null
    sys.stdout.flush()
    sys.stderr.flush()
    si = open(os.devnull, 'r')
    so = open(os.devnull, 'a+')
    se = open(os.devnull, 'a+')
    os.dup2(si.fileno(), sys.stdin.fileno())
    os.dup2(so.fileno(), sys.stdout.fileno())
    os.dup2(se.fileno(), sys.stderr.fileno())

    return(0)

def main():
    """
    Start the daemon.
    """
    ret = 0
    cfg = 'ludolph.cfg'
    cfg_fp = None
    cfg_lo = ((os.path.expanduser('~'), '.'+ cfg),
            (sys.prefix, 'etc', cfg), ('/etc', cfg))
    config = RawConfigParser()
    config_base_sections = ('global', 'xmpp')

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
        sys.stderr.write("""\nLudolph can't start!\n
You need to create a config file in one this locations: \n%s\n
You can rename ludolph.cfg.example and update the required variables.
The example file is located in: %s\n\n""" % (
        '\n'.join([os.path.join(*i) for i in cfg_lo]),
        os.path.dirname(os.path.abspath(__file__))))
        sys.exit(1)

    # Prepare logging configuration
    logconfig = {
        'level': logging.getLevelName(config.get('global','loglevel')),
        'format': LOGFORMAT,
    }

    if config.has_option('global', 'logfile'):
        logfile = config.get('global','logfile').strip()
        if logfile:
            logconfig['filename'] = logfile

    # Daemonize
    if config.has_option('global', 'daemon'):
        if config.getboolean('global', 'daemon'):
            ret = daemonize()
            # Save pid file
            try:
                with open(config.get('global', 'pidfile'), 'w') as fp:
                    fp.write('%s' % os.getpid())
            except Exception as ex:
                # Setup logging just to show this error
                logging.basicConfig(**logconfig)
                logger.critical('Could not write to pidfile (%s)\n', ex)
                sys.exit(1)

    # Setup logging
    logging.basicConfig(**logconfig)

    # All exceptions will be logged
    def log_except_hook(*exc_info):
        logger.critical('Unhandled exception!', exc_info=exc_info)
        #sys.exit(99)
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

    # Load plugins
    plugins = {}
    for plugin in config.sections():
        plugin = plugin.lower().strip()
        if plugin in config_base_sections:
            continue
        logger.info('Loading plugin: %s', plugin)
        try:
            clsname = plugin[0].upper() + plugin[1:]
            modname = 'ludolph.plugins.'+ plugin
            module = __import__(modname, fromlist=[clsname])
            plugins[modname] = getattr(module, clsname)
        except Exception as ex:
            logger.critical('Could not load plugin %s', plugin)
            logger.exception(ex)

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
    try:
        os.remove(pipe_file)
    except:
        pass

    os.mkfifo(pipe_file, int(pipe_mode, 8))

    # Here we go
    try:
        xmpp = LudolphBot(config, plugins=plugins)
        signal.signal(signal.SIGINT, xmpp.shutdown)
        signal.signal(signal.SIGTERM, xmpp.shutdown)
        if xmpp.connect(tuple(address), use_tls=use_tls, use_ssl=use_ssl):
            xmpp.process(block=True)
            sys.exit(ret)
        else:
            logger.error('Ludolph is unable to connect to jabber server')
            sys.exit(2)
    finally:
        # Cleanup
        logger.info('Removing pipe file %s', pipe_file)
        os.remove(pipe_file)


if __name__ == '__main__':
    main()
