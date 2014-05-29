"""
Ludolph: Monitoring Jabber Bot
Copyright (C) 2014 Erigones s. r. o.
This file is part of Ludolph.

See the LICENSE file for copying permission.
"""
import logging
import socket
from functools import wraps
# noinspection PyUnresolvedReferences
from bottle import Bottle, ServerAdapter, abort, request

__all__ = ('WebServer', 'webhook')

logger = logging.getLogger(__name__)


class LudolphBottle(Bottle):
    """
    Bottle web server - used for webhooks.
    """
    def default_error_handler(self, res):
        return 'ERROR %s: %s\n' % (res.status_code, res.body)


WEBAPP = LudolphBottle()
WEBHOOKS = {}  # webhook : (module, path)


class WebServer(ServerAdapter):
    """
    Like bottle.WSGIRefServer, but with stop() method.
    """
    server = None
    quiet = True
    webhooks = WEBHOOKS

    def run(self, handler):
        logger.info('Starting web server on http://%s:%s', self.host, self.port)
        from wsgiref.simple_server import WSGIRequestHandler, WSGIServer
        from wsgiref.simple_server import make_server

        class CustomHandler(WSGIRequestHandler):
            def address_string(self):  # Prevent reverse DNS lookups
                return self.client_address[0]

            def log_error(self, *args, **kwargs):
                kwargs['level'] = logging.ERROR  # Change default log level
                self.log_message(*args, **kwargs)

            def log_message(self, fmt, *args, **kwargs):  # Log into default log file instead of stderr
                level = kwargs.get('level', logging.INFO)
                logger.log(level, '%s - - %s', self.client_address[0], fmt % args)

        handler_cls = self.options.get('handler_class', CustomHandler)
        server_cls = self.options.get('server_class', WSGIServer)

        if ':' in self.host:  # Fix wsgiref for IPv6 addresses
            if getattr(server_cls, 'address_family') == socket.AF_INET:
                # noinspection PyPep8Naming
                class server_cls(server_cls):
                    address_family = socket.AF_INET6

        self.server = make_server(self.host, self.port, handler, server_cls, handler_cls)
        self.server.serve_forever()

    def stop(self):
        logger.info('Stopping web server')
        if self.server:
            self.server.shutdown()

    def start(self):
        global WEBAPP
        WEBAPP.run(server=self)

    def reset_webhooks(self):
        logger.info('Reinitializing webhooks')
        self.webhooks.clear()

    def reset_webapp(self):
        if self.server:
            logger.info('Reinitializing web server')
            global WEBAPP
            del WEBAPP
            WEBAPP = LudolphBottle()
            self.server.set_app(WEBAPP)

    def display_webhooks(self):
        """Return list of available webhooks suitable for logging"""
        return ['%s [%s]: %s' % (name, hook[0].split('.')[-1], hook[1]) for name, hook in self.webhooks.items()]


def _webview(fun):
    """
    Wrapper for bottle callbacks responsible for finding back the bound method. Inspired by err bot.
    """
    @wraps(fun)
    def wrap(*args, **kwargs):
        from ludolph.bot import PLUGINS

        try:
            obj = PLUGINS[WEBHOOKS[fun.__name__][0]]
            obj_fun = getattr(obj, fun.__name__)
        except (KeyError, AttributeError) as e:
            logger.error('Requested webhook "%s" is not registered (%s)', fun.__name__, e)
            abort(404, 'Webhook vanished')
        else:
            return obj_fun(*args, **kwargs)

    return wrap


def webhook(path, methods=('GET',)):
    """
    Decorator for registering HTTP request handlers. Inspired by err bot.
    """
    def webhook_decorator(fun):
        if fun.__name__ in WEBHOOKS:
            logger.critical('Webhook "%s" from plugin "%s" overlaps with existing webhook from module "%s"',
                            fun.__name__, fun.__module__, WEBHOOKS[fun.__name__][0])
            return None

        logging.debug('Registering web hook "%s" from plugin "%s" to URL "%"', fun.__name__, fun.__module__, path)
        WEBAPP.route(path, methods, _webview(fun))
        WEBHOOKS[fun.__name__] = (fun.__module__, path)

        return fun

    return webhook_decorator
