"""
This is a port of the ruby zabbix api found here:
http://trac.red-tux.net/browser/ruby/api/zbx_api.rb

LGPL 2.1   http://www.gnu.org/licenses/old-licenses/lgpl-2.1.html

Zabbix API Python Library.
Original Ruby Library is Copyright (C) 2009 Andrew Nelson nelsonab(at)red-tux(dot)net
Python Library is Copyright (C) 2009 Brett Lentz brett.lentz(at)gmail(dot)com
                  Copyright (C) 2013 Erigones s. r. o. erigones(at)erigones(dot)com

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

import base64
import hashlib
import logging
import re
import datetime
import json
import time

try:
    import urllib2
except ImportError:
    # noinspection PyUnresolvedReferences,PyPep8Naming
    import urllib.request as urllib2  # python3

from collections import deque


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


def hide_auth(msg):
    """Remove sensitive information from msg."""
    for pattern, repl in RE_HIDE_AUTH:
        msg = pattern.sub(repl, msg)

    return msg


class ZabbixAPIException(Exception):
    """
    Generic zabbix api exception.
    code list:
         -32602 - Invalid params (eg already exists)
         -32500 - no permissions
    """
    def __init__(self, message, *args, **kwargs):
        message = hide_auth(message)  # Remove sensitive information
        super(ZabbixAPIException, self).__init__(message, *args, **kwargs)


class AlreadyExists(ZabbixAPIException):
    """
    Zabbix object already exists.
    """
    pass


class ZabbixAPI(object):
    __username__ = None
    __password__ = None
    auth = ''
    params = None
    method = None
    id = 0

    def __init__(self, server='http://localhost/zabbix', user=None, passwd=None,
                 log_level=logging.WARNING, timeout=10, r_query_len=10, **kwargs):
        """
        Create an API object.
        We're going to use proto://server/path to find the JSON-RPC api.
        :param str server: Server to connect to
        :param str path: Path leading to the zabbix install
        :param str user: Optional HTTP auth username
        :param str passwd: Optional HTTP auth password
        :param int log_level: Logging level
        :param int timeout: Timeout for HTTP requests to api
        :param int r_query_len: Max length of query history
        :param **kwargs: Data to pass to each api module
        """
        self.logger = logging.getLogger(PARENT_LOGGER)
        self.set_log_level(log_level)
        self.server = server
        self.url = server + '/api_jsonrpc.php'
        self.proto = server.split('://')[0]
        self.httpuser = user
        self.httppasswd = passwd
        self.timeout = timeout
        self.r_query = deque([], maxlen=r_query_len)

        # sub-class instances
        self.usergroup = ZabbixAPISubClass(self, dict({'prefix': 'usergroup'}, **kwargs))
        self.user = ZabbixAPISubClass(self, dict({'prefix': 'user'}, **kwargs))
        self.host = ZabbixAPISubClass(self, dict({'prefix': 'host'}, **kwargs))
        self.item = ZabbixAPISubClass(self, dict({'prefix': 'item'}, **kwargs))
        self.hostgroup = ZabbixAPISubClass(self, dict({'prefix': 'hostgroup'}, **kwargs))
        self.hostinterface = ZabbixAPISubClass(self, dict({'prefix': 'hostinterface'}, **kwargs))
        self.application = ZabbixAPISubClass(self, dict({'prefix': 'application'}, **kwargs))
        self.trigger = ZabbixAPISubClass(self, dict({'prefix': 'trigger'}, **kwargs))
        self.template = ZabbixAPISubClass(self, dict({'prefix': 'template'}, **kwargs))
        self.action = ZabbixAPISubClass(self, dict({'prefix': 'action'}, **kwargs))
        self.alert = ZabbixAPISubClass(self, dict({'prefix': 'alert'}, **kwargs))
        self.info = ZabbixAPISubClass(self, dict({'prefix': 'info'}, **kwargs))
        self.event = ZabbixAPISubClass(self, dict({'prefix': 'event'}, **kwargs))
        self.graph = ZabbixAPISubClass(self, dict({'prefix': 'graph'}, **kwargs))
        self.graphitem = ZabbixAPISubClass(self, dict({'prefix': 'graphitem'}, **kwargs))
        self.map = ZabbixAPISubClass(self, dict({'prefix': 'map'}, **kwargs))
        self.screen = ZabbixAPISubClass(self, dict({'prefix': 'screen'}, **kwargs))
        self.script = ZabbixAPISubClass(self, dict({'prefix': 'script'}, **kwargs))
        self.usermacro = ZabbixAPISubClass(self, dict({'prefix': 'usermacro'}, **kwargs))
        self.drule = ZabbixAPISubClass(self, dict({'prefix': 'drule'}, **kwargs))
        self.history = ZabbixAPISubClass(self, dict({'prefix': 'history'}, **kwargs))
        self.maintenance = ZabbixAPISubClass(self, dict({'prefix': 'maintenance'}, **kwargs))
        self.proxy = ZabbixAPISubClass(self, dict({'prefix': 'proxy'}, **kwargs))
        self.apiinfo = ZabbixAPISubClass(self, dict({'prefix': 'apiinfo'}, **kwargs))
        self.configuration = ZabbixAPISubClass(self, dict({'prefix': 'configuration'}, **kwargs))
        self.dcheck = ZabbixAPISubClass(self, dict({'prefix': 'dcheck'}, **kwargs))
        self.dhost = ZabbixAPISubClass(self, dict({'prefix': 'dhost'}, **kwargs))
        self.discoveryrule = ZabbixAPISubClass(self, dict({'prefix': 'discoveryrule'}, **kwargs))
        self.dservice = ZabbixAPISubClass(self, dict({'prefix': 'dservice'}, **kwargs))
        self.iconmap = ZabbixAPISubClass(self, dict({'prefix': 'iconmap'}, **kwargs))
        self.image = ZabbixAPISubClass(self, dict({'prefix': 'image'}, **kwargs))
        self.mediatype = ZabbixAPISubClass(self, dict({'prefix': 'mediatype'}, **kwargs))
        self.service = ZabbixAPISubClass(self, dict({'prefix': 'service'}, **kwargs))
        self.templatescreen = ZabbixAPISubClass(self, dict({'prefix': 'templatescreen'}, **kwargs))
        self.usermedia = ZabbixAPISubClass(self, dict({'prefix': 'usermedia'}, **kwargs))
        self.hostinterface = ZabbixAPISubClass(self, dict({'prefix': 'hostinterface'}, **kwargs))
        self.triggerprototype = ZabbixAPISubClass(self, dict({'prefix': 'triggerprototype'}, **kwargs))
        self.graphprototype = ZabbixAPISubClass(self, dict({'prefix': 'graphprototype'}, **kwargs))
        self.itemprototype = ZabbixAPISubClass(self, dict({'prefix': 'itemprototype'}, **kwargs))
        self.webcheck = ZabbixAPISubClass(self, dict({'prefix': 'webcheck'}, **kwargs))
        self.trends = ZabbixAPISubClass(self, dict({'prefix': 'trends'}, **kwargs))

        self.debug('url: %s', self.url)

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
        return self.log(logging.DEBUG, msg, *args)

    def json_obj(self, method, params=None):
        if params is None:
            params = {}

        obj = {
            'jsonrpc': '2.0',
            'method': method,
            'params': params,
            'auth': self.auth,
            'id': self.id
        }
        self.debug('json_obj: %s', obj)

        return json.dumps(obj)

    def login(self, user=None, password=None, save=True):
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
        obj = self.json_obj('user.authenticate', {'user': l_user, 'password': l_password})
        result = self.do_request(obj)
        self.auth = result['result']

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
            self.log(logging.ERROR, 'Unable to decode. returned string: %s', reads)
            raise ZabbixAPIException('Unable to decode response: ' + str(e))

        self.debug('Response Body: %s', jobj)
        self.id += 1

        if 'error' in jobj:  # some exception
            msg = 'Error %s: %s, %s while sending %s' % (jobj['error']['code'], jobj['error']['message'],
                                                         jobj['error']['data'], str(json_obj))

            if re.search('.*already\sexists.*', jobj['error']['data'], re.I):  # already exists
                raise AlreadyExists(msg, jobj['error']['code'])
            else:
                raise ZabbixAPIException(msg, jobj['error']['code'])

        return jobj

    def api_version(self, **options):
        self.check_auth()
        obj = self.do_request(self.json_obj('APIInfo.version', options))

        return obj['result']

    def check_auth(self):
        if not self.logged_in():
            raise ZabbixAPIException('Not logged in.')


class ZabbixAPISubClass(object):
    """
    Wrapper class to ensure all calls go through the parent object.
    """
    def __init__(self, parent, data, **kwargs):
        self.data = data
        self.parent = parent
        self.parent.debug('Creating %s', self.__class__.__name__)

        # Save any extra info passed in
        for key, val in kwargs.items():
            setattr(self, key, val)

    def __getattr__(self, name):
        if self.data['prefix'] == 'configuration' and name == 'import_':  # workaround for "import" method
            name = 'import'

        def method(*opts):
            return self.universal('%s.%s' % (self.data['prefix'], name), opts[0])
        return method

    def universal(self, method, opts):
        """
        Check authentication and perform actual API request and re-login if needed.
        """
        start_time = time.time()
        self.parent.check_auth()
        self.parent.log(logging.INFO, '[%s-%05d] Calling Zabbix API method "%s"', start_time, self.parent.id, method)
        self.parent.log(logging.DEBUG, '\twith options: %s', opts)

        try:
            return self.parent.do_request(self.parent.json_obj(method, opts))['result']
        except ZabbixAPIException as ex:
            if str(ex).find('Not authorized while sending') >= 0:
                self.parent.log(logging.WARNING, 'Zabbix API not logged in (%s). Performing Zabbix API re-login', ex)
                try:
                    self.parent.auth = ''  # reset auth before re-login
                    self.parent.login()
                except ZabbixAPIException as e:
                    self.parent.log(logging.ERROR, 'Zabbix API login error (%s)', e)
                    self.parent.auth = ''  # logged_in() will always return False
                    raise e
                else:
                    return self.parent.do_request(self.parent.json_obj(method, opts))['result']
            else:
                raise ex
        finally:
            self.parent.log(logging.INFO, '[%s-%05d] Zabbix API method "%s" finished in %g seconds',
                            start_time, self.parent.id, method, (time.time() - start_time))
