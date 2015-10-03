"""
Ludolph: Monitoring Jabber bot
Copyright (C) 2012-2015 Erigones, s. r. o.
This file is part of Ludolph.

See the file LICENSE for copying permission.
"""
import logging
import re
from datetime import datetime, timedelta
from sleekxmpp.xmlstream import ET
from sleekxmpp.stanza import Message
try:
    from xml.etree.ElementTree import ParseError
except ImportError:
    from xml.parsers.expat import ExpatError as ParseError

__all__ = ('red', 'green', 'blue', 'IncomingLudolphMessage', 'OutgoingLudolphMessage')

logger = logging.getLogger(__name__)
r = re.compile

TEXT2BODY = (
    (r(r'\*\*(.+?)\*\*'), r'*\1*'),
    (r(r'__(.+?)__'), r'\1'),
    (r(r'\^\^(.+?)\^\^'), r'\1'),
    (r(r'~~(.+?)~~'), r'\1'),
    (r(r'%{(.+?)}(.+)%'), r'\2'),
    (r(r'\[\[(.+?)\|(.+?)\]\]'), r'\1'),
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
    (r(r'\[\[(.+?)\|(.+?)\]\]'), r'<a href="\1">\2</a>'),
    (r(r'%{(.+?)}(.+?)%'), r'<span style="\1">\2</span>'),
    (r(r'(ERROR)'), r'<span style="color:#FF0000;">\1</span>'),
    (r(r'(PROBLEM|OFF)'), r'<span style="color:#FF0000;"><strong>\1</strong></span>'),
    (r(r'(OK|ON)'), r'<span style="color:#00FF00;"><strong>\1</strong></span>'),
    (r(r'([Dd]isaster)'), r'<span style="color:#FF0000;"><strong>\1</strong></span>'),
    (r(r'([Cc]ritical)'), r'<span style="color:#FF3300;"><strong>\1</strong></span>'),
    (r(r'([Hh]igh)'), r'<span style="color:#FF6600;"><strong>\1</strong></span>'),
    (r(r'([Aa]verage)'), r'<span style="color:#FF9900;"><strong>\1</strong></span>'),
    (r(r'([Ww]arning)'), r'<span style="color:#FFCC00;"><strong>\1</strong></span>'),
    # (r(r'([Ii]nformation)'), r'<span style="color:#FFFF00;"><strong>\1</strong></span>'),
    (r(r'(Monitored)'), r'<span style="color:#00FF00;"><strong>\1</strong></span>'),
    (r(r'(Not\ monitored)'), r'<span style="color:#FF0000;"><strong>\1</strong></span>'),
    ('\n', '<br/>\n'),
)


class MessageError(Exception):
    """
    Error while creating new XMPP message.
    """
    pass


def red(s):
    return '%%{color:#FF0000}%s%%' % s


def green(s):
    return '%%{color:#00FF00}%s%%' % s


def blue(s):
    return '%%{color:#0000FF}%s%%' % s


# noinspection PyAttributeOutsideInit
class IncomingLudolphMessage(Message):
    """
    SleekXMPP Message object wrapper.
    """
    _ludolph_attrs = ('reply_output', 'stream_output')

    @classmethod
    def wrap_msg(cls, msg):
        """Inject our properties into original Message object"""
        if isinstance(msg, cls):
            raise TypeError('Message object is already wrapped')

        obj = cls()
        obj.__class__ = type(msg.__class__.__name__, (cls, msg.__class__), {})
        obj.__dict__ = msg.__dict__

        return obj

    def dump(self):
        data = {}

        # The underlying ElementBase object does not implement the dict interface properly
        for k in self.interfaces:
            v = self.get(k, None)

            if v is not None:
                data[k] = str(v)

        # Add our custom attributes
        for i in self._ludolph_attrs:
            data[i] = getattr(self, i)

        return data

    @classmethod
    def load(cls, data):
        from ludolph.bot import get_xmpp

        obj = cls(stream=get_xmpp())

        # First set our custom attributes
        for i in cls._ludolph_attrs:
            try:
                setattr(obj, i, data.pop(i))
            except KeyError:
                continue

        # The all other ElementBase items
        for k, v in data.items():
            obj[k] = v

        return obj

    def _get_ludolph_attr(self, attr, default, set_default=False):
        try:
            return getattr(self, attr)
        except AttributeError:
            if set_default:
                setattr(self, attr, default)
            return default

    def get_reply_output(self, default=True, set_default=False):
        return self._get_ludolph_attr('_reply_output_', default, set_default=set_default)

    def set_reply_output(self, value):
        self._reply_output_ = value

    reply_output = property(get_reply_output, set_reply_output)

    def get_stream_output(self, default=False, set_default=False):
        return self._get_ludolph_attr('_stream_output_', default, set_default=set_default)

    def set_stream_output(self, value):
        self._stream_output_ = value

    stream_output = property(get_stream_output, set_stream_output)


class OutgoingLudolphMessage(object):
    """
    Creating and sending bots messages (replies).
    """
    def __init__(self, mbody, mhtml=None, mtype=None, msubject=None, delay=None, timestamp=None):
        """
        Construct message body in plain text and html.
        """
        self.mtype = mtype
        self.msubject = msubject

        if mbody is not None:
            self.mbody = self._text2body(str(mbody))

        if mhtml is None and mbody is not None:
            self.mhtml = self._text2html(str(mbody))
        else:
            self.mhtml = str(mhtml)

        if delay:
            timestamp = datetime.utcnow() + timedelta(seconds=delay)

        self.timestamp = timestamp

    @staticmethod
    def _replace(replist, text):
        """
        Helper for replacing text parts according to replist.
        """
        for rx, te in replist:
            # noinspection PyProtectedMember
            if isinstance(rx, re._pattern_type):
                try:
                    text = rx.sub(te, text)
                except re.error as exc:
                    logger.error('Regexp error during message text replacement: %s', exc)
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
            # noinspection PyUnresolvedReferences
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

    def send(self, xmpp, mto, mfrom=None, mnick=None):
        """
        Send a new message.
        """
        msg = xmpp.make_message(mto, self.mbody, msubject=self.msubject, mtype=self.mtype, mhtml=self.mhtml,
                                mfrom=mfrom, mnick=mnick)

        if self.timestamp:
            msg['delay'].set_stamp(self.timestamp)

        return msg.send()

    def reply(self, msg, clear=True):
        """
        Send a reply to incoming msg.
        """
        msg.reply(self.mbody, clear=clear)
        msg['html']['body'] = self.mhtml

        if self.timestamp:
            msg['delay'].set_stamp(self.timestamp)

        return msg.send()


LudolphMessage = OutgoingLudolphMessage  # Backward compatibility
