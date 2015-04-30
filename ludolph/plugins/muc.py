import logging
from sleekxmpp.exceptions import IqError

from ludolph import __version__
from ludolph.command import CommandError, PermissionDenied, command
from ludolph.web import webhook, request, abort
from ludolph.plugins.plugin import LudolphPlugin

logger = logging.getLogger(__name__)


class Muc(LudolphPlugin):
    """
    Multi-user chat room commands.
    """
    __version__ = __version__
    room_motd = None
    persistent_attrs = ('room_motd',)

    def __init__(self, xmpp, config, reinit=False, **kwargs):
        """Do not load the plugin if the room option is disabled"""
        if not xmpp.room:
            raise RuntimeError('Multi-user chat support is disabled in config file')

        super(Muc, self).__init__(xmpp, config, reinit=reinit, **kwargs)

    def _get_nick(self, user):
        """Get nick from JID or nick and check if user is in chat room"""
        nick = None

        if '@' in user:
            nick = self.xmpp.get_room_nick(user)
        elif self.xmpp.is_nick_in_room(user):
            nick = user

        return nick

    @command(user_required=False, room_user_required=True, room_admin_required=True)
    def invite(self, msg, user=None):
        """
        Invite user or yourself to multi-user chat room (room admin only).

        Usage: invite [JID]
        """
        if not user:
            user = self.xmpp.get_jid(msg)

        if not self.xmpp.is_jid_room_user(user):
            raise CommandError('User **%s** is not allowed to access the MUC room' % user)

        self.xmpp.muc.invite(self.xmpp.room, user)

        return 'Inviting **%s** to MUC room %s' % (user, self.xmpp.room)

    # noinspection PyUnusedLocal
    @command(user_required=False, room_user_required=True, room_admin_required=True)
    def kick(self, msg, user):
        """
        Kick user from multi-user chat room (room admin only).

        Usage: kick <JID>
        """
        nick = self._get_nick(user)

        if not nick:
            raise CommandError('User **%s** is not in MUC room' % user)

        try:
            self.xmpp.muc.setRole(self.xmpp.room, nick, 'none')
        except (IqError, ValueError) as e:
            err = getattr(e, 'condition', str(e))
            raise CommandError('User **%s** could not be kicked from MUC room: __%s__' % (user, err))

        return 'User **%s** kicked from MUC room' % user

    @command(user_required=False, room_user_required=True)
    def motd(self, msg, action=None):
        """
        Show, set or remove message of the day.

        Show message of the day (room user only).
        Usage: motd

        Set message of the day (room admin only).
        Usage: motd set <text>

        Delete message of the day and disable automatic announcements (room admin only).
        Usage: motd del
        """
        if action:
            if not self.xmpp.is_jid_room_admin(self.xmpp.get_jid(msg)):
                raise PermissionDenied

            if action == 'del':
                self.room_motd = None
                return 'MOTD successfully deleted'
            elif action == 'set':
                try:
                    text = msg['body'].split(' ', 2)[2].strip()
                    if not text:
                        raise IndexError
                except IndexError:
                    raise CommandError('Missing text')
                else:
                    self.room_motd = text
                    return 'MOTD successfully updated'
            else:
                raise CommandError('Invalid action')

        if self.room_motd is None:
            return '(MOTD disabled)'
        else:
            return self.room_motd

    @webhook('/room', methods=('POST',))
    def roomtalk(self):
        """
        Send message to chat room.
        """
        msg = request.forms.get('msg', None)

        if not msg:
            logger.warning('Missing msg parameter in room request')
            abort(400, 'Missing msg parameter')

        self.xmpp.msg_send(self.xmpp.room, msg, mtype='groupchat')

        return 'Message sent'
