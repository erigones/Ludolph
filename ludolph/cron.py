"""
Ludolph: Monitoring Jabber Bot
Original Library: Copyright (C) 2011 JS Lee (https://github.com/jsleetw/crontab.py)
Ludolph Modification: Copyright (C) 2014-2015 Erigones, s. r. o.
This file is part of Ludolph.

See the LICENSE file for copying permission.
"""
import logging
import time
from datetime import datetime, timedelta
from functools import wraps

try:
    from collections import OrderedDict
except ImportError:
    # noinspection PyUnresolvedReferences,PyPackageRequirements
    from ordereddict import OrderedDict

__all__ = ('cronjob',)

logger = logging.getLogger(__name__)


class CronStar(set):
    """Universal set - match everything"""
    def __contains__(self, item):
        return True
star = CronStar()


def at_fun(job, fun):
    """
    Decorator for "at" job commands.
    """
    @wraps(fun)
    def wrap(msg, *args, **kwargs):
        kwargs['_reply_output'] = False  # Do not send command output to job owner
        ret = fun(msg, *args, **kwargs)
        out = 'Scheduled job **%s** run at %s finished with output: %s' % (job.name, datetime.now().isoformat(), ret)
        fun.__self__.xmpp.msg_reply(msg, out)  # We will inform the owner here
        return out
    return wrap


class CronJob(object):
    """
    Crontab entry.
    """
    def __init__(self, name, fun, args=(), kwargs=(), minute=None, hour=None, day=None, month=None, dow=None,
                 onetime=False, owner=None, at=False):
        if at:
            fun = at_fun(self, fun)

        self.name = name
        self.fun = fun
        self.args = args
        self.kwargs = dict(kwargs)
        self.minutes = self.validate_field(minute, 0, 59)
        self.hours = self.validate_field(hour, 0, 23)
        self.days = self.validate_field(day, 1, 31)
        self.months = self.validate_field(month, 1, 12)
        self.dow = self.validate_field(dow, 0, 6)
        self.onetime = self.clean_datetime(onetime)
        self.owner = owner
        self.at = at

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, self.name)

    @property
    def schedule(self):
        """String representation of cron/onetime schedule"""
        if self.onetime:
            return self.onetime.isoformat()

        j = lambda x: ','.join(map(str, x)) or '*'
        return '%s %s %s %s %s' % (j(self.minutes), j(self.hours), j(self.days), j(self.months), j(self.dow))

    @property
    def plugin(self):
        """Return plugin name"""
        return self.fun.__module__.split('.')[-1]

    @property
    def fqfn(self):
        """Fully qualified function name"""
        return '%s.%s' % (self.fun.__module__, self.fun.__name__)

    @property
    def command(self):
        """String representation of job command with all arguments"""
        if self.at and self.args:
            return self.args[0]['body']

        cmd = [self.fun.__name__.replace('_', '-')]

        if self.args:
            cmd.extend(map(str, self.args))

        if self.kwargs:
            cmd.extend(['%s=%s' % kv for kv in self.kwargs.items()])

        return ' '.join(cmd)

    @staticmethod
    def clean_datetime(dt):
        """Return datetime object without seconds"""
        if dt:
            return datetime(*dt.timetuple()[:5])
        return None

    def display(self):
        """Return string representation of this cron job suitable for logging"""
        return '%s: %s [%s]: %s' % (self.name, self.command, self.plugin, self.schedule)

    # noinspection PyMethodMayBeStatic
    def validate_value(self, value, min_value, max_value):
        """Each date/time field must be a number in specified range"""
        num = int(value)

        if num > max_value or num < min_value:
            raise ValueError('Value not in range')

        return num

    def validate_field(self, value, min_value, max_value):
        """Simple validation of crontab fields"""
        if value is None or value == '*':
            return star

        if isinstance(value, int):
            value = (value,)
        elif not (value and getattr(value, '__iter__', False)):
            raise ValueError('Invalid date/time field')

        validate = self.validate_value

        return set([validate(i, min_value, max_value) for i in value])

    def match_time(self, dt):
        """Return True if this event should trigger at the specified datetime"""
        if self.onetime:
            return self.onetime <= dt
        return ((dt.minute in self.minutes) and (dt.hour in self.hours) and (dt.day in self.days) and
                (dt.month in self.months) and (dt.weekday() in self.dow))

    def run(self):
        """Go!"""
        return self.fun(*self.args, **self.kwargs)


class CronTab(OrderedDict):
    """
    "List" of crontab entries. Each entry is identified by a unique name.
    """
    def add(self, name, fun, **kwargs):
        """Add named crontab entry, which will run fun at specified date/time"""
        assert name not in self, 'Cron job with name "%s" is already defined' % name
        job = CronJob(name, fun, **kwargs)
        self[name] = job

        return job

    def delete(self, name):
        """Delete named crontab entry"""
        return self.pop(name)

    def generate_id(self):
        """Generate new job ID for a new onetime ("at") job"""
        try:
            last = int(self.keys()[-1])
        except (IndexError, ValueError):
            return 1
        else:
            return last + 1

    def add_onetime(self, fun, onetime, **kwargs):
        """Add onetime job into crontab"""
        kwargs['onetime'] = onetime

        return self.add(self.generate_id(), fun, **kwargs)

    def add_at(self, fun, onetime, msg, owner):
        """Add "at" onetime job into crontab"""
        return self.add_onetime(fun, onetime, args=(msg,), owner=owner, at=True)


CRONJOBS = CronTab()


class Cron(object):
    """
    Cron thread (the scheduler).
    """
    running = False
    crontab = CRONJOBS

    def run(self):
        logger.info('Starting cron')
        dt = CronJob.clean_datetime(datetime.now())
        self.running = True

        while self.running:
            for name, job in self.crontab.items():
                if job.match_time(dt):
                    logger.info('Running cron job "%s" (%s) with schedule "%s" as user "%s"',
                                name, job.fqfn, job.schedule, job.owner)

                    try:
                        res = job.run()
                    except Exception as ex:
                        logger.critical('Error while running cron job "%s" (%s)', name, job.fqfn)
                        logger.exception(ex)
                        continue
                    finally:
                        if job.onetime:
                            self.crontab.delete(name)

                    logger.info('Cron job "%s" (%s) output: "%s"', name, job.fqfn, res)

            dt += timedelta(minutes=1)

            while self.running and datetime.now() < dt:
                time.sleep(5)

    def stop(self):
        logger.info('Stopping cron')
        self.running = False

    def reset(self):
        logger.info('Reinitializing crontab')
        self.crontab.clear()

    def display_cronjobs(self):
        """Return list of available cron jobs suitable for logging"""
        return (job.display() for job in self.crontab.values())


def _cronjob(fun):
    """
    Wrapper cron job function responsible for finding back the bound method.
    """
    @wraps(fun)
    def wrap(*args, **kwargs):
        from ludolph.bot import PLUGINS

        try:
            obj = PLUGINS[CRONJOBS[fun.__name__].fun.__module__]
            obj_fun = getattr(obj, fun.__name__)
        except (KeyError, AttributeError) as e:
            logger.error('Cron job "%s" is not registered (%s)', fun.__name__, e)
            return None
        else:
            return obj_fun(*args, **kwargs)

    return wrap


def cronjob(minute='*', hour='*', day='*', month='*', dow='*'):
    """
    Decorator for creating crontab entries.
    """
    def cronjob_decorator(fun):
        if fun.__name__ in CRONJOBS:
            logger.critical('Cron job "%s" from plugin "%s" overlaps with existing cron job from module "%s"',
                            fun.__name__, fun.__module__, CRONJOBS[fun.__name__].fun.__module__)
            return None

        logging.debug('Registering cron job "%s" from plugin "%s" to run at "%s %s %s %s %s"',
                      fun.__name__, fun.__module__, minute, hour, day, month, dow)
        CRONJOBS.add(fun.__name__, _cronjob(fun), minute=minute, hour=hour, day=day, month=month, dow=dow)

        return fun

    return cronjob_decorator
