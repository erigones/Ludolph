import logging
import shlex
from types import MethodType
from subprocess import Popen, PIPE, STDOUT

from ludolph import __version__
from ludolph.command import CommandError, command, parameter_required, admin_required
from ludolph.plugins.plugin import LudolphPlugin

logger = logging.getLogger(__name__)


class Process(Popen):
    """
    Command wrapper.
    """
    def __init__(self, args):
        super(Process, self).__init__(args, stdout=PIPE, stderr=STDOUT, close_fds=True, bufsize=0)

    @property
    def output(self):
        """Stdout generator"""
        while self.poll() is None:
            yield self.stdout.readline().decode('utf-8').rstrip('\n')

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

    def __init__(self, xmpp, config, **kwargs):
        super(Commands, self).__init__(xmpp, config, **kwargs)
        self.init()

    @staticmethod
    def _parse_config_line(name, value):
        """Parse one config value"""
        value = value.strip().split(',')
        cmd = value.pop(0).strip()
        decorators = []
        command_kwargs = {}
        doc = ''

        for i, opt in enumerate(value):
            opt = opt.strip()

            if opt == 'command':
                continue
            elif opt == 'stream_output':
                command_kwargs['stream_output'] = True
            elif opt == 'ignore_output':
                command_kwargs['reply_output'] = False
            elif opt == 'admin_required':
                decorators.append(admin_required)
            elif opt.startswith('parameter_required('):
                try:
                    n = int(opt.split('(')[-1][:-1])
                except ValueError:
                    logger.error('Could not parse dynamic command "%s" value "%s"', name, opt)
                    continue
                else:
                    decorators.append(parameter_required(n))
            else:
                doc = ','.join(value[i:]).strip()
                break

        # The @command decorator must be always first
        decorators.insert(0, command(**command_kwargs))

        return cmd, decorators, doc

    @staticmethod
    def _get_fun(name, cmd, decorators, doc):
        """Return dynamic function"""
        # noinspection PyProtectedMember
        fun = lambda obj, msg, *args: obj._execute(msg, name, cmd, *args)
        fun.__name__ = name
        fun.__doc__ = doc

        for decorator in decorators:
            fun = decorator(fun)

        return fun

    def init(self):
        """Initialize commands from config file"""
        logger.debug('Initializing dynamic commands')

        for name, value in self.config.items():
            try:
                fun_name = name.strip().replace('-', '_')
                fun = self._get_fun(fun_name, *self._parse_config_line(name, value))

                if fun:
                    logger.info('Registering dynamic command: %s', name)
                    setattr(self, fun_name, MethodType(fun, self))
                else:
                    raise ValueError('Error while decorating dynamic command function')
            except Exception as e:
                logger.error('Dynamic command "%s" could not be registered (%s)', name, e)

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def _execute(self, msg, name, cmd, *args, **kwargs):
        """Execute a command and return stdout or raise CommandError"""
        try:
            cmd = shlex.split(cmd)
            cmd.extend(map(str, args))
        except Exception:
            raise CommandError('Could not parse command parameters')

        logger.info('Running dynamic command: %s', cmd)

        try:
            return Process(cmd).cmd_output(name, stream=msg.stream_output)
        except Exception as e:
            raise CommandError('Could not run command (%s)' % e)
