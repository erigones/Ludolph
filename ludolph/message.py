"""
Ludolph: Monitoring Jabber bot
Copyright (C) 2012-13 Erigones s. r. o.
This file is part of Ludolph.

See the file LICENSE for copying permission.
"""
from tabulate import tabulate as _tabulate

TABLEFMT = 'rst'

__all__ = ['tabulate', 'LudolphMessage']


def tabulate(*args, **kwargs):
    """
    Tabulate wrapper.
    """
    if 'tablefmt' not in kwargs:
        kwargs['tablefmt'] = TABLEFMT

    return _tabulate(*args, **kwargs)


class LudolphMessage(object):
    """
    Creating and sending bot's messages (replies).
    """
    def __init__(self, mbody, mhtml=None, mtype=None):
        """
        Construct message body in plain text and html.
        """
        self.mbody = mbody
        self.mhtml = mhtml
        self.mtype = mtype

        #if mhtml is None and mbody is not None:
        #    mhtml = mbody
        #self.mhtml = '<code><pre>%s</pre></code>' % mhtml

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
