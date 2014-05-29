"""
Ludolph: Monitoring Jabber bot
Copyright (C) 2012-2014 Erigones s. r. o.
This file is part of Ludolph.

See the file LICENSE for copying permission.
"""
import json
import logging
# noinspection PyPackageRequirements
import requests

from ludolph.command import command, parameter_required, admin_required
from ludolph.message import red, green, blue
from ludolph.plugins.plugin import LudolphPlugin

logger = logging.getLogger(__name__)


class Erigones(LudolphPlugin):
    """
    Erigones API commands. EXPERIMENTAL.

    https://my.erigones.com/static/api/doc/

    Add to ludolph.cfg::

        [erigones]
        api_url = https://my.erigones.com/api
        username = username@example.com
        password = Passw0rd

    """

    user_agent = 'es/0.3/ludolph'
    methods = {
        'get':      requests.get,
        'create':   requests.post,
        'set':      requests.put,
        'delete':   requests.delete,
        'options':  requests.options,
    }
    actions = methods.keys()
    timeout = None
    headers = {
        'User-Agent': user_agent,
        'Accept': 'application/json; indent=4',
        'Content-Type': 'application/json; indent=4',
    }

    # noinspection PyMissingConstructor,PyUnusedLocal
    def __init__(self, xmpp, config, **kwargs):
        """
        Initialize configuration and login to erigones.
        """
        self.xmpp = xmpp
        config = dict(config)

        try:
            self.api_url = config['api_url'].rstrip('/')
            self.credentials = {'username': config['username'], 'password': config['password']}
        except KeyError:
            logger.error('Erigones plugin configuration missing')
            raise

        self._login()

    def __es(self, action, resource, params=None, data=None, msg=None):
        """
        The es http request. Returns (status_code, response_text).
        """
        url = self.api_url + resource
        response_text = ''
        r = self.methods[action](url=url, headers=self.headers, timeout=self.timeout,
                                 params=params, data=data, allow_redirects=False, stream=True)
        status_code = r.status_code

        if 'task_id' in r.headers:  # Task status stream
            msg_body = 'Waiting for pending task %s ...' % blue(r.headers['task_id'])
            self.xmpp.msg_send(msg['from'].bare, msg_body, mtype=msg['type'])

            for i in r.iter_content():
                if not i.isspace():
                    text = i + r.text
                    text = text.strip().split('\n')
                    status_code = int(text.pop())
                    response_text = '\n'.join(text)
                    break

        else:
            response_text = r.text

        try:
            response_text = json.loads(response_text)
        except ValueError:
            pass

        return status_code, response_text

    def _logout(self):
        """
        Logout from Erigones API.
        """
        logger.debug('Signing out of Erigones API')
        status, text = self.__es('get', '/accounts/logout/')

        if status == 200:
            logger.info('Logout successful: "%s"', text)
            self.headers.pop('Authorization', None)
        else:
            logger.warning('Logout problem (%s): "%s"', status, text)

    def _login(self):
        """
        Login to Erigones API.
        """
        logger.debug('Signing in to Erigones API')
        self.headers.pop('Authorization', None)
        status, text = self.__es('create', '/accounts/login/', data=json.dumps(self.credentials))

        if status == 200 and isinstance(text, dict) and 'token' in text:
            logger.info('Login successful: "%s"', text['detail'])
            self.headers['Authorization'] = 'Token ' + text['token']
        else:
            logger.error('Login problem (%s): "%s"', status, text)

    def _is_authenticated(self):
        """
        Return True if authorization token exists.
        """
        return 'Authorization' in self.headers

    def _es(self, msg, action, resource, *parameters):
        """
        The es command. Returns (status_code, response_text).
        """
        if action not in self.actions:
            return 0, 'ERROR: Bad action'

        if not resource or resource[0] != '/':
            return 0, 'ERROR: Missing resource'

        params = None
        data = None
        options = {}

        if parameters:  # Parse arguments
            key = None
            val_next = False

            for i in parameters:
                if i and i[0] == '-':
                    key = i[1:]
                    options[key] = True
                    val_next = True
                    continue

                if val_next and key:
                    _i = str(i).lower()

                    if _i == 'false':
                        options[key] = False
                    elif _i == 'true':
                        options[key] = True
                    elif _i == 'null':
                        options[key] = None
                    else:
                        options[key] = i

                    key = None
                    val_next = False

        if action == 'get' or action == 'logout':
            params = options
        else:
            data = json.dumps(options)

        if resource[-1] != '/':
            resource += '/'

        def workbitch():  # Perform one re-login if needed
            if not self._is_authenticated():
                logger.error('Erigones API not available')
                return 0, 'ERROR: Erigones API not available'

            return self.__es(action, resource, params=params, data=data, msg=msg)

        status, res = workbitch()

        if status == 403 and res.get('detail') == 'Authentication credentials were not provided.':
            logger.warning('Performing re-login to Erigones API')
            self._login()
            return workbitch()

        return status, res

    @admin_required
    @parameter_required(2)
    @command
    def es(self, msg, action, resource, *parameters):
        """
        es - Swiss Army Knife for Erigones API (EXPERIMENTAL)

        Usage: es action [/resource] [parameters]

          action:\t{get|create|set|delete|options}
          resource:\t/some/resource/in/api
          parameters:\t-foo baz -bar qux ...
        """
        status, text = self._es(msg, action, resource, *parameters)

        if not status:
            return text

        out = {
            'action': action,
            'resource': resource,
            '**status**': status,
            '**text**': text,
        }

        return json.dumps(out, indent=4)

    # noinspection PyTypeChecker
    @admin_required
    @command
    def vm_list(self, msg):
        """
        Show a list of all servers.

        Usage: vm-list
        """
        code, res = self._es(msg, 'get', '/vm/status')

        if code != 200:
            return str(res)

        out = []

        for vm in res['result']:
            if vm['status'] == 'running':
                color = green
            elif vm['status'] == 'stopped' or vm['status'] == 'stopping':
                color = red
            elif vm['status'] == 'pending':
                color = blue
            else:
                color = lambda x: x

            out.append('**%s** (%s)\t%s\t(%d)' % (vm['hostname'], vm['alias'], color(vm['status']), len(vm['tasks'])))

        out.append('\n**%d** servers are shown.' % len(res['result']))

        return '\n'.join(out)
