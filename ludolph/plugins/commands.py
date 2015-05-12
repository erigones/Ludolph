import logging
import shlex
import os
from types import MethodType
from subprocess import Popen, PIPE, STDOUT

from ludolph import __version__
from ludolph.command import CommandError, command
from ludolph.plugins.plugin import LudolphPlugin

logger = logging.getLogger(__name__)

COMMAND_FLAGS = {
    'stream_output': ('stream_output', True),
    'reply_output': ('reply_output', True),
    'ignore_output': ('reply_output', False),
    'user_not_required': ('user_required', False),
    'user_required': ('user_required', True),
    'admin_required': ('admin_required', True),
    'room_user_required': ('room_user_required', True),
    'room_admin_required': ('room_admin_required', True),
}


class Process(Popen):
    """
    Command wrapper.
    """
    def __init__(self, args):
        super(Process, self).__init__(args, stdout=PIPE, stderr=STDOUT, stdin=open(os.devnull, 'wb'),
                                      close_fds=True, bufsize=0)

    @property
    def output(self):
        """Stdout generator"""
        with self.stdout:
            for line in iter(self.stdout.readline, b''):
                yield line.decode('utf-8').rstrip('\n')
        self.wait()

    # noinspection PyUnusedLocal
    def _get_output(self, name):
        """Classic Ludolph command output"""
        out = '\n'.join(self.output)

        if self.returncode == 0:
            return out
        else:
            raise CommandError(out)

    def _get_output_stream(self, name):
        """Stream Ludolph command output"""
        for line in self.output:
            yield line

        if self.returncode != 0:
            raise CommandError('Command "%s" exited with non-zero status %s' % (name, self.returncode))

    def cmd_output(self, name, stream=False):
        """Return output suitable for Ludolph commands"""
        if stream:
            return self._get_output_stream(name)
        else:
            return self._get_output(name)


class Commands(LudolphPlugin):
    """
    Create dynamic Ludolph commands associated with real OS commands and scripts.
    """
    __version__ = __version__

    def __init__(self, *args, **kwargs):
        super(Commands, self).__init__(*args, **kwargs)
        self.init()

    @staticmethod
    def _parse_config_line(value, **command_kwargs):
        """Parse one config value"""
        value = value.strip().split(',')
        cmd = value.pop(0).strip()
        doc = ''

        for i, opt in enumerate(value):
            opt = opt.strip()

            if opt == 'command':
                continue
            elif opt in COMMAND_FLAGS:
                cmd_flag = COMMAND_FLAGS[opt]
                command_kwargs[cmd_flag[0]] = cmd_flag[1]
            else:
                doc = ','.join(value[i:]).strip()
                break

        return cmd, command(**command_kwargs), doc

    @staticmethod
    def _get_fun(name, cmd, command_decorator, doc):
        """Return dynamic function"""
        # noinspection PyProtectedMember
        fun = lambda obj, msg, *args: obj._execute(msg, name, cmd, *args)
        fun.__name__ = name
        fun.__doc__ = doc

        return command_decorator(fun)

    def init(self):
        """Initialize commands from config file"""
        logger.debug('Initializing dynamic commands')

        for name, value in self.config.items():
            try:
                fun_name = name.strip().replace('-', '_')

                if fun_name == 'pass_through':
                    _, cmd_decorator, doc = self._parse_config_line(value, parse_parameters=False)
                    fun = self._get_fun(fun_name, None, cmd_decorator, doc)
                else:
                    fun = self._get_fun(fun_name, *self._parse_config_line(value))

                if fun:
                    logger.info('Registering dynamic command: %s', name)
                    setattr(self, fun_name, MethodType(fun, self))
                else:
                    raise ValueError('Error while decorating dynamic command function')
            except Exception as e:
                logger.error('Dynamic command "%s" could not be registered (%s)', name, e)

    @property
    def _pass_through_mode(self):
        return bool(getattr(self, 'pass_through', False))

    def __post_init__(self):
        if self._pass_through_mode:
            logger.warning('You have enabled pass-through mode in the commands plugin. '
                           '_ALL_ bot commands will be passed to the operating system!')
            # Override fallback message handler
            # noinspection PyUnresolvedReferences
            self.xmpp.fallback_message = self.pass_through
            # No need for a "pass-through" command
            del self.xmpp.commands['pass-through']

    def __destroy__(self):
        if self._pass_through_mode:
            # Recover original fallback message handler
            self.xmpp.fallback_message = self.xmpp.original_fallback_message

    # noinspection PyMethodMayBeStatic
    def _execute(self, msg, name, cmd, *args):
        """Execute a command and return stdout or raise CommandError"""
        try:
            if cmd is None:  # pass-through mode
                cmd = shlex.split(msg['body'])
            else:
                cmd = shlex.split(cmd)
                cmd.extend(map(str, args))
        except Exception:
            raise CommandError('Could not parse command parameters')

        logger.info('Running dynamic command: %s', cmd)

        try:
            return Process(cmd).cmd_output(name, stream=msg.stream_output)
        except CommandError:
            raise
        except Exception as e:
            raise CommandError('Could not run command (%s)' % e)
