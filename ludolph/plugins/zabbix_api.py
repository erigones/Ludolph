"""
This is a port of the ruby zabbix api found here:
http://trac.red-tux.net/browser/ruby/api/zbx_api.rb

LGPL 2.1   http://www.gnu.org/licenses/old-licenses/lgpl-2.1.html

Zabbix API Python Library.
Original Ruby Library is Copyright (C) 2009 Andrew Nelson nelsonab(at)red-tux(dot)net
Python Library is Copyright (C) 2009 Brett Lentz brett.lentz(at)gmail(dot)com
                  Copyright (C) 2013-2015 Erigones, s. r. o. erigones(at)erigones(dot)com
                  Copyright (C) 2014-2015 https://github.com/gescheit/scripts

This library is free software; you can redistribute it and/or
modify it under the terms of the GNU Lesser General Public
License as published by the Free Software Foundation; either
version 2.1 of the License, or (at your option) any later version.

This library is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public
License along with this library; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA


NOTES:
The API requires zabbix 1.8 or later.
Currently, not all of the API is implemented, and some functionality is broken. This is a work in progress.
"""
from logging import getLogger, DEBUG, INFO, WARNING, ERROR
from collections import deque
import base64
import hashlib
import re
import datetime
import json
import time

try:
    import urllib2
except ImportError:
    # noinspection PyUnresolvedReferences,PyPep8Naming
    import urllib.request as urllib2  # python3

PARENT_LOGGER = __name__
DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
TRIGGER_SEVERITY = (
    'not_classified',
    'information',
    'warning',
    'average',
    'high',
    'disaster',
)
RE_HIDE_AUTH = (
    (re.compile(r'("auth": )".*?"'), r'\1"***"'),
    (re.compile(r'("password": )".*?"'), r'\1"***"'),
)
RELOGIN_INTERVAL = 60  # seconds


def hide_auth(msg):
    """Remove sensitive information from msg."""
    for pattern, repl in RE_HIDE_AUTH:
        msg = pattern.sub(repl, msg)

    return msg


class ZabbixAPIException(Exception):
    """
    Generic zabbix API exception.
    """
    def __init__(self, msg):
        super(ZabbixAPIException, self).__init__(hide_auth(msg))  # Remove sensitive information


class ZabbixAPIError(ZabbixAPIException):
    """
    Structured zabbix API error.

    Code list:
         -32602 - Invalid params (eg already exists)
         -32500 - no permissions
    """
    _error_template = {'code': -1, 'message': None, 'data': None}

    def __init__(self, msg, **kwargs):
        self.error = dict(self._error_template, **kwargs)
        super(ZabbixAPIError, self).__init__(msg)


class ZabbixAPI(object):
    __username__ = None
    __password__ = None
    auth = ''
    params = None
    method = None
    id = 0
    last_login = None

    def __init__(self, server='http://localhost/zabbix', user=None, passwd=None,
                 log_level=WARNING, timeout=10, r_query_len=10):
        """
        Create an API object.
        We're going to use proto://server/path to find the JSON-RPC api.
        :param str server: Server URL to connect to
        :param str user: Optional HTTP auth username
        :param str passwd: Optional HTTP auth password
        :param int log_level: Logging level
        :param int timeout: Timeout for HTTP requests to api
        :param int r_query_len: Max length of query history
        """
        self.logger = getLogger(PARENT_LOGGER)
        self.set_log_level(log_level)
        self.server = server
        self.url = server + '/api_jsonrpc.php'
        self.proto = server.split('://')[0]
        self.httpuser = user
        self.httppasswd = passwd
        self.timeout = timeout
        self.r_query = deque([], maxlen=r_query_len)
        self.debug('url: %s', self.url)

    def __getattr__(self, name):
        api_method = ZabbixAPISubClass(self, name)
        setattr(self, name, api_method)

        return api_method

    def set_log_level(self, level):
        self.debug('Set logging level to %d', level)
        self.logger.setLevel(level)

    @classmethod
    def get_severity(cls, prio):
        """
        Return severity string from severity id.
        """
        try:
            return TRIGGER_SEVERITY[int(prio)]
        except IndexError:
            return 'unknown'

    @classmethod
    def get_datetime(cls, timestamp):
        """
        Return python datetime object from unix timestamp.
        """
        return datetime.datetime.fromtimestamp(int(timestamp))

    @classmethod
    def convert_datetime(cls, dt, dt_format=DATETIME_FORMAT):
        """
        Convert python datetime to human readable date and time string.
        """
        return dt.strftime(dt_format)

    @classmethod
    def timestamp_to_datetime(cls, dt, dt_format=DATETIME_FORMAT):
        """
        Convert unix timestamp to human readable date/time string.
        """
        return cls.convert_datetime(cls.get_datetime(dt), dt_format=dt_format)

    @classmethod
    def get_age(cls, dt):
        """
        Calculate delta between current time and datetime and return a human readable form of the delta object.
        """
        delta = datetime.datetime.now() - dt
        days = delta.days
        hours, rem = divmod(delta.seconds, 3600)
        minutes, seconds = divmod(rem, 60)

        if days:
            return '%dd %dh %dm' % (days, hours, minutes)
        else:
            return '%dh %dm %ds' % (hours, minutes, seconds)

    def recent_query(self):
        """
        Return recent query.
        """
        return list(self.r_query)

    def log(self, level, msg, *args):
        return self.logger.log(level, msg, *args)

    def debug(self, msg, *args):
        return self.log(DEBUG, msg, *args)

    def json_obj(self, method, params=None, auth=True):
        if params is None:
            params = {}

        obj = {
            'jsonrpc': '2.0',
            'method': method,
            'params': params,
            'auth': self.auth if auth else None,
            'id': self.id,
        }

        self.debug('json_obj: %s', obj)

        return json.dumps(obj)

    def login(self, user=None, password=None, save=True):
        self.last_login = time.time()

        if user and password:
            l_user = user
            l_password = password
            if save:
                self.__username__ = user
                self.__password__ = password

        elif self.__username__ and self.__password__:
            l_user = self.__username__
            l_password = self.__password__

        else:
            raise ZabbixAPIException('No authentication information available.')

        # Don't print the raw password.
        hashed_pw_string = 'md5(' + hashlib.md5(l_password.encode('utf-8')).hexdigest() + ')'
        self.debug('Trying to login with %s:%s', repr(l_user), repr(hashed_pw_string))
        obj = self.json_obj('user.login', {'user': l_user, 'password': l_password}, auth=False)
        result = self.do_request(obj)
        self.auth = result['result']

    def relogin(self):
        try:
            self.auth = ''  # reset auth before relogin
            self.login()
        except ZabbixAPIException as e:
            self.log(ERROR, 'Zabbix API relogin error (%s)', e)
            self.auth = ''  # logged_in() will always return False
            raise

    def logged_in(self):
        return bool(self.auth)

    def test_login(self):
        if self.auth:
            obj = self.json_obj('user.checkAuthentication', {'sessionid': self.auth})
            result = self.do_request(obj)

            if 'result' in result and result['result']:
                return True  # auth hash good
            else:
                self.auth = ''  # auth hash bad

        return False

    def do_request(self, json_obj):
        headers = {
            'Content-Type': 'application/json-rpc',
            'User-Agent': 'python/zabbix_api',
        }

        if self.httpuser:
            self.debug('HTTP Auth enabled')
            x = self.httpuser + ':' + self.httppasswd
            auth = base64.b64encode(x.encode('utf-8'))
            headers['Authorization'] = 'Basic ' + auth.decode('ascii')

        self.r_query.append(str(json_obj))
        self.debug('Sending: %s', json_obj)
        self.debug('Sending headers: %s', headers)

        request = urllib2.Request(url=self.url, data=json_obj.encode('utf-8'), headers=headers)

        if self.proto == 'https':
            http_handler = urllib2.HTTPSHandler(debuglevel=0)
        elif self.proto == 'http':
            http_handler = urllib2.HTTPHandler(debuglevel=0)
        else:
            raise ZabbixAPIException('Unknown protocol %s' % self.proto)

        opener = urllib2.build_opener(http_handler)
        urllib2.install_opener(opener)

        try:
            response = opener.open(request, timeout=self.timeout)
        except Exception as e:
            raise ZabbixAPIException('HTTP connection problem: ' + str(e))

        self.debug('Response Code: %s', response.code)

        # NOTE: Getting a 412 response code means the headers are not in the list of allowed headers.
        if response.code != 200:
            raise ZabbixAPIException('HTTP error %s: %s' % (response.status, response.reason))

        reads = response.read()

        if len(reads) == 0:
            raise ZabbixAPIException('Received zero answer')

        try:
            jobj = json.loads(reads.decode('utf-8'))
        except ValueError as e:
            self.log(ERROR, 'Unable to decode. returned string: %s', reads)
            raise ZabbixAPIException('Unable to decode response: ' + str(e))

        self.debug('Response Body: %s', jobj)
        self.id += 1

        if 'error' in jobj:  # zabbix API error
            error = jobj['error']

            if isinstance(error, dict):
                try:
                    msg = 'Error %s: %s, %s while sending %s' % (error['code'], error['message'], error['data'],
                                                                 str(json_obj))
                except KeyError:
                    msg = '%s' % error

                raise ZabbixAPIError(msg, **error)

        return jobj

    def api_version(self, **options):
        self.check_auth()
        obj = self.do_request(self.json_obj('apiinfo.version', options, auth=False))

        return obj['result']

    def check_auth(self):
        if not self.logged_in():
            if self.last_login and (time.time() - self.last_login) > RELOGIN_INTERVAL:
                self.log(WARNING, 'Zabbix API not logged in. Performing Zabbix API relogin after %d seconds',
                         RELOGIN_INTERVAL)
                self.relogin()  # Will raise exception in case of login error
            else:
                raise ZabbixAPIException('Not logged in.')


class ZabbixAPISubClass(object):
    """
    Wrapper class to ensure all calls go through the parent object.
    """
    def __init__(self, parent, prefix):
        self.prefix = prefix
        self.parent = parent
        self.log = self.parent.log
        self.log(DEBUG, 'Creating %s', self.__class__.__name__)

    def __getattr__(self, name):
        if self.prefix == 'configuration' and name == 'import_':  # workaround for "import" method
            name = 'import'

        def method(*opts):
            return self.universal('%s.%s' % (self.prefix, name), opts[0])
        return method

    def universal(self, method, opts):
        """
        Check authentication and perform actual API request and relogin if needed.
        """
        start_time = time.time()
        self.parent.check_auth()
        self.log(INFO, '[%s-%05d] Calling Zabbix API method "%s"', start_time, self.parent.id, method)
        self.log(DEBUG, '\twith options: %s', opts)

        try:
            return self.parent.do_request(self.parent.json_obj(method, opts))['result']
        except ZabbixAPIException as ex:
            if str(ex).find('Not authorized while sending') >= 0:
                self.log(WARNING, 'Zabbix API not logged in (%s). Performing Zabbix API relogin', ex)
                self.parent.relogin()  # Will raise exception in case of login error
                return self.parent.do_request(self.parent.json_obj(method, opts))['result']
            else:
                raise ex
        finally:
            self.log(INFO, '[%s-%05d] Zabbix API method "%s" finished in %g seconds',
                     start_time, self.parent.id, method, (time.time() - start_time))
