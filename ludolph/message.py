"""
Ludolph: Monitoring Jabber bot
Copyright (C) 2012-13 Erigones s. r. o.
This file is part of Ludolph.

See the file LICENSE for copying permission.
"""
import re
import logging
from textile import Textile
from textile.functions import _normalize_newlines
from sleekxmpp.xmlstream import ET


__all__ = ['tabulate', 'LudolphMessage']

logger = logging.getLogger(__name__)
r = re.compile

HTMLSTYLE = ''
TEXTILE = (
        (r(r'(PROBLEM|OFF)'), r'%{color:#FF0000}*\1*%'),
        (r(r'(OK|ON)'), r'%{color:#00FF00}*\1*%'),
        (r(r'([Dd]isaster)'), r'%{color:#FF0000}*\1*%'),
        (r(r'([Cc]ritical)'), r'%{color:#FF3300}*\1*%'),
        (r(r'([Hh]igh)'), r'%{color:#FF6600}*\1*%'),
        (r(r'([Aa]verage)'), r'%{color:#FF9900}*\1*%'),
        (r(r'([Ww]arning)'), r'%{color:#FFCC00}*\1*%'),
        #(r(r'([Ii]nformation)'), r'%{color:#FFFF00}*\1*%'),
        (r(r'(Monitored)'), r'%{color:#00FF00}*\1*%'),
        (r(r'(Not\ monitored)'), r'%{color:#FF0000}*\1*%'),
)


def tabulate(data, *args, **kwargs):
    """
    Tabulate wrapper.
    """
    return '\n'.join(['\t'.join(row) for row in data])


class LudolphMessage(object):
    """
    Creating and sending bot's messages (replies).
    """
    t = Textile(restricted=False)

    def __init__(self, mbody, mhtml=None, mtype=None):
        """
        Construct message body in plain text and html.
        """
        self.mbody = mbody
        self.mhtml = mhtml
        self.mtype = mtype

        if mbody is not None:
            self.mbody = self._text2body(mbody)

        if mhtml is None and mbody is not None:
            self.mhtml = self._text2html(mbody)

    def _replace(self, replist, text):
        """
        Helper for replacing text parts according to replist.
        """
        for r, t in replist:
            if isinstance(r, basestring):
                text = text.replace(r, t)
            else:
                text = r.sub(t, text)

        return text

    def _text2body(self, text):
        """
        Remove tags from text.
        """
        return text  # TODO

    def _text2html(self, text):
        """
        Convert text to html.
        """
        html = _normalize_newlines(text)
        html = self._replace(TEXTILE, html)
        html = self.t.encode_html(html)
        #html = self.t.block(html)
        html = self.t.span(html)
        html = self._replace([('\n', '<br/>\n')], html)
        html = '<div style="%s">\n%s\n</div>' % (HTMLSTYLE, html)

        try:
            return ET.XML(html)
        except ET.ParseError as e:
            logger.error('Could not parse html: %s', e)
            return None

    @classmethod
    def create(cls, mbody, **kwargs):
        """
        Return LudolphMessage instance.
        """
        if isinstance(mbody, cls):
            return mbody

        return cls(mbody, **kwargs)

    def send(self, xmpp, mto):
        """
        Send a new message.
        """
        msg = xmpp.make_message(mto, self.mbody, mtype=self.mtype, mhtml=self.mhtml)

        return msg.send()

    def reply(self, msg, clear=True):
        """
        Send a reply to incoming msg.
        """
        msg.reply(self.mbody, clear=clear)
        msg['html']['body'] = self.mhtml

        return msg.send()
