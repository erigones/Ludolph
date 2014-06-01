"""
Ludolph: Monitoring Jabber Bot
Original Library: Copyright (C) 2011 JS Lee (https://github.com/jsleetw/crontab.py)
Ludolph Modification: Copyright (C) 2014 Erigones s. r. o.
This file is part of Ludolph.

See the LICENSE file for copying permission.
"""
import logging
import time
from datetime import datetime, timedelta
from functools import wraps

__all__ = ('cronjob',)

logger = logging.getLogger(__name__)


class CronStar(set):
    """Universal set - match everything"""
    def __contains__(self, item):
        return True
star = CronStar()


class CronJob(object):
    """
    Crontab entry.
    """
    def __init__(self, fun, args=(), kwargs=(), minute=None, hour=None, day=None, month=None, dow=None):
        self.fun = fun
        self.args = args
        self.kwargs = dict(kwargs)
        self.minutes = self.validate_field(minute, 0, 59)
        self.hours = self.validate_field(hour, 0, 23)
        self.days = self.validate_field(day, 1, 31)
        self.months = self.validate_field(month, 1, 12)
        self.dow = self.validate_field(dow, 0, 6)

    @property
    def schedule(self):
        """String representation of cron schedule"""
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

        if isinstance(value, (int, long)):
            value = (value,)
        elif not (value and getattr(value, '__iter__', False)):
            raise ValueError('Invalid date/time field')

        validate = self.validate_value

        return set([validate(i, min_value, max_value) for i in value])

    def match_time(self, dt):
        """Return True if this event should trigger at the specified datetime"""
        return ((dt.minute in self.minutes) and (dt.hour in self.hours) and (dt.day in self.days) and
                (dt.month in self.months) and (dt.weekday() in self.dow))

    def run(self):
        """Go!"""
        return self.fun(*self.args, **self.kwargs)


class CronTab(dict):
    """
    "List" of crontab entries. Each entry is identified by a unique name.
    """
    def add(self, name, fun, **kwargs):
        """Add named crontab entry, which will run fun at specified date/time"""
        self[name] = CronJob(fun, **kwargs)

    def delete(self, name):
        """Delete named crontab entry"""
        del self[name]


CRONJOBS = CronTab()


class Cron(object):
    """
    Cron thread (the scheduler).
    """
    running = False
    crontab = CRONJOBS

    def run(self):
        logger.info('Starting cron')
        dt = datetime(*datetime.now().timetuple()[:5])
        self.running = True

        while self.running:
            for name, job in self.crontab.items():
                if job.match_time(dt):
                    logger.info('Running cron job "%s" (%s) with schedule "%s"', name, job.fqfn, job.schedule)
                    res = job.run()
                    logger.debug('\tCron job "%s" output: "%s"', name, res)

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
        return ['%s [%s]: %s' % (name, job.plugin, job.schedule) for name, job in self.crontab.items()]


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