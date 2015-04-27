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
from collections import namedtuple

try:
    from collections import OrderedDict
except ImportError:
    # noinspection PyUnresolvedReferences,PyPackageRequirements
    from ordereddict import OrderedDict

from ludolph.message import IncomingLudolphMessage

__all__ = ('cronjob',)

logger = logging.getLogger(__name__)

noop = lambda *args, **kwargs: None

CronJobFun = namedtuple('CronJobFun', ('name', 'module'))


def at_fun(job, fun):
    """
    Decorator for "at" job command functions.
    """
    @wraps(fun)
    def wrap(msg, *args, **kwargs):
        msg.reply_output = False  # Do not send command output to job owner
        ret = fun(msg, *args, **kwargs)
        out = 'Scheduled job **%s** run at %s finished with output:\n%s' % (job.name, datetime.now().isoformat(), ret)
        fun.__self__.xmpp.msg_reply(msg, out)  # We will inform the owner here
        return out
    return wrap


class CronStar(set):
    """Universal set - match everything"""
    def __contains__(self, item):
        return True
star = CronStar()


class CronJobError(Exception):
    pass


class CronJob(object):
    """
    Crontab entry.
    """
    def __init__(self, name, fun, args=(), kwargs=(), minute=None, hour=None, day=None, month=None, dow=None,
                 onetime=False, owner=None, at=False):
        if not isinstance(fun, CronJobFun):
            raise TypeError('fun must be a instance of CronJobFun')

        self.name = name
        self._fun = fun
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
        return self._fun.module.split('.')[-1]

    @property
    def fqfn(self):
        """Fully qualified function name"""
        return '%s.%s' % (self._fun.module, self._fun.name)

    @property
    def command(self):
        """String representation of job command with all arguments"""
        if self.at and self.args:
            return self.args[0].get('body')

        cmd = [self._fun.name.replace('_', '-')]

        if self.args:
            cmd.extend(map(str, self.args))

        if self.kwargs:
            cmd.extend(['%s=%s' % kv for kv in self.kwargs.items()])

        return ' '.join(cmd)

    @property
    def fun(self):
        """Get the real fun - the plugin object's bound method"""
        from ludolph.bot import PLUGINS

        try:
            obj = PLUGINS[self._fun.module]
            obj_fun = getattr(obj, self._fun.name)
        except (KeyError, AttributeError):
            raise CronJobError('%r lost its fun' % self)

        if self.at:
            obj_fun = at_fun(self, obj_fun)

        return obj_fun

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
        fun = self.fun

        try:
            if self.at:
                return fun(IncomingLudolphMessage.load(self.args[0]))
            else:
                return fun(*self.args, **self.kwargs)
        except CronJobError as e:
            logger.error('Error while running cron job "%s" (%s): %s', self.name, self.fqfn, e)
            return None


class CronTab(OrderedDict):
    """
    "List" of crontab entries. Each entry is identified by a unique name.
    """
    db_sync = noop  # Run after add()/delete() operations.

    # noinspection PyMethodOverriding
    def __repr__(self):
        return '%s(jobs=%s)' % (self.__class__.__name__, len(self))

    def __reduce__(self):
        """Pickle only onetime cron jobs"""
        clean_crontab = self.__class__((name, job) for name, job in self.items() if job.onetime)
        return super(CronTab, clean_crontab).__reduce__()

    def __setitem__(self, key, value, **kwargs):
        if not isinstance(value, CronJob):
            raise TypeError('value must be a instance of CronJob')

        return super(CronTab, self).__setitem__(key, value, **kwargs)

    def sync(self):
        try:
            self.db_sync()
        except Exception as ex:
            logger.critical('Could not sync crontab with persistent DB file: %s', ex)

    def add(self, name, fun, **kwargs):
        """Add named crontab entry, which will run fun at specified date/time"""
        if name in self:
            raise NameError('Cron job with name "%s" is already defined' % name)

        if not hasattr(fun, '__call__'):
            raise ValueError('fun must be a callable function')

        job = CronJob(name, CronJobFun(fun.__name__, fun.__module__), **kwargs)
        self[name] = job

        if job.onetime:
            self.sync()

        return job

    def delete(self, name):
        """Delete named crontab entry"""
        job = self.pop(name)

        if job.onetime:
            self.sync()

        return job

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
        return self.add_onetime(fun, onetime, args=(msg.dump(),), owner=owner, at=True)

    def clear_cron_jobs(self):
        """Remove all cron jobs, but keep onetime jobs"""
        for name, job in self.items():
            if not job.onetime:
                del self[name]

    def display_cron_jobs(self):
        """Return list of available non-onetime cron jobs suitable for logging"""
        return (job.display() for job in self.values() if not job.onetime)


CRONJOBS = CronTab()


class Cron(object):
    """
    Cron thread (the scheduler).
    """
    running = False
    crontab = CRONJOBS
    db = None

    def __init__(self, db=None):
        """Enable DB support if available"""
        if db is not None:
            self.db_enable(db)

    def db_set_crontab(self):
        if self.db is not None:
            self.db['crontab'] = self.crontab

    def db_enable(self, db):
        self.db = db
        cronjobs = db.get('crontab', None)

        if cronjobs:
            logger.info('Loading %d cron jobs from persistent DB file', len(cronjobs))
            self.crontab.update(cronjobs)

        self.db_set_crontab()
        self.crontab.db_sync = db.sync

    def db_disable(self):
        self.db = None
        self.crontab.db_sync = noop

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
        self.db_set_crontab()
        self.running = False

    def reset(self):
        logger.info('Reinitializing crontab')
        self.db_set_crontab()
        self.crontab.clear_cron_jobs()

    def display_cronjobs(self):
        return self.crontab.display_cron_jobs()


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
        CRONJOBS.add(fun.__name__, fun, minute=minute, hour=hour, day=day, month=month, dow=dow)

        return fun

    return cronjob_decorator
