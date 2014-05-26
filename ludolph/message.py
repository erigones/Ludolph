"""
Ludolph: Monitoring Jabber bot
Copyright (C) 2012-2014 Erigones s. r. o.
This file is part of Ludolph.

See the file LICENSE for copying permission.
"""
import logging
import re
from sleekxmpp.xmlstream import ET
try:
    from xml.etree.ElementTree import ParseError
except ImportError:
    from xml.parsers.expat import ExpatError as ParseError

__all__ = ('red', 'green', 'blue', 'LudolphMessage')

logger = logging.getLogger(__name__)
r = re.compile

TEXT2BODY = (
    (r(r'\*\*(.+?)\*\*'), r'*\1*'),
    (r(r'__(.+?)__'), r'\1'),
    (r(r'\^\^(.+?)\^\^'), r'\1'),
    (r(r'~~(.+?)~~'), r'\1'),
    (r(r'%{(.+?)}(.+)%'), r'\2'),
)

TEXT2HTML = (
    ('&', '&#38;'),
    ('<', '&#60;'),
    ('>', '&#62;'),
    ("'", '&#39;'),
    ('"', '&#34;'),
    (r(r'\*\*(.+?)\*\*'), r'<b>\1</b>'),
    (r(r'__(.+?)__'), r'<i>\1</i>'),
    (r(r'\^\^(.+?)\^\^'), r'<sup>\1</sup>'),
    (r(r'~~(.+?)~~'), r'<sub>\1</sub>'),
    (r(r'%{(.+?)}(.+)%'), r'<span style="\1">\2</span>'),
    (r(r'(ERROR)'), r'<span style="color:#FF0000;">\1</span>'),
    (r(r'(PROBLEM|OFF)'), r'<span style="color:#FF0000;"><strong>\1</strong></span>'),
    (r(r'(OK|ON)'), r'<span style="color:#00FF00;"><strong>\1</strong></span>'),
    (r(r'([Dd]isaster)'), r'<span style="color:#FF0000;"><strong>\1</strong></span>'),
    (r(r'([Cc]ritical)'), r'<span style="color:#FF3300;"><strong>\1</strong></span>'),
    (r(r'([Hh]igh)'), r'<span style="color:#FF6600;"><strong>\1</strong></span>'),
    (r(r'([Aa]verage)'), r'<span style="color:#FF9900;"><strong>\1</strong></span>'),
    (r(r'([Ww]arning)'), r'<span style="color:#FFCC00;"><strong>\1</strong></span>'),
    #(r(r'([Ii]nformation)'), r'<span style="color:#FFFF00;"><strong>\1</strong></span>'),
    (r(r'(Monitored)'), r'<span style="color:#00FF00;"><strong>\1</strong></span>'),
    (r(r'(Not\ monitored)'), r'<span style="color:#FF0000;"><strong>\1</strong></span>'),
    ('\n', '<br/>\n'),
)


def red(s):
    return '%%{color:#FF0000}%s%%' % s


def green(s):
    return '%%{color:#00FF00}%s%%' % s


def blue(s):
    return '%%{color:#0000FF}%s%%' % s


class LudolphMessage(object):
    """
    Creating and sending bot's messages (replies).
    """
    mbody = None
    mhtml = None
    mtype = None

    def __init__(self, mbody, mhtml=None, mtype=None):
        """
        Construct message body in plain text and html.
        """
        self.mtype = mtype

        if mbody is not None:
            self.mbody = self._text2body(str(mbody))

        if mhtml is None and mbody is not None:
            self.mhtml = self._text2html(str(mbody))
        else:
            self.mhtml = str(mhtml)

    @staticmethod
    def _replace(replist, text):
        """
        Helper for replacing text parts according to replist.
        """
        for rx, te in replist:
            # noinspection PyProtectedMember
            if isinstance(rx, re._pattern_type):
                text = rx.sub(te, text)
            else:
                text = text.replace(rx, te)

        return text

    def _text2body(self, text):
        """
        Remove tags from text.
        """
        body = self._replace(TEXT2BODY, text.strip())

        return body

    def _text2html(self, text):
        """
        Convert text to html.
        """
        html = self._replace(TEXT2HTML, text.strip())
        html = '<div>\n' + html + '\n</div>'

        try:
            return ET.XML(html)
        except (ParseError, SyntaxError) as e:
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
