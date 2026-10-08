import logging

from odoo import _, api, models, modules
from odoo.exceptions import UserError
from odoo.modules.registry import Registry

_logger = logging.getLogger(__name__)


class MailConversation(models.Model):
    """Inbox-viewer-specific GTD action entry points (task #3965). These
    take plain ids (not recordsets) so the OWL inbox client can call them
    directly by RPC without a prior ``browse``/``read``.
    """

    _inherit = "mail.conversation"

    @api.model
    def action_dismiss(self, transport_id, external_id):
        """GTD **hide** (the viewer's "Hide" button; RPC name unchanged) --
        remove an inbox item from the list. It never touches the real
        mailbox (use ``archive_item`` / ``trash_item`` for that): the
        message stays in the mailbox and comes back on the next browse.
        Ingest-on-action means nothing is persisted until a human files an
        item (AC5) -- so if this ``external_id`` was never captured,
        hiding it is a pure client-side action (the item simply isn't
        filed). If it *was* already captured (e.g. the user replied to it
        earlier, then comes back to hide it), archive that *conversation*
        instead of silently doing nothing.

        :return: True if an existing conversation was archived, False if
            this was a no-op (item was never filed).
        """
        transport = self.env["conversation.transport"].browse(transport_id)
        conversation = self._find_captured(transport, external_id)
        if conversation:
            conversation.action_archive()
        return bool(conversation)

    @api.model
    def _inbox_archive_after_capture(self, transport, external_id):
        """Archive the source message in the real mailbox once it has been
        filed in Odoo, when the transport's ``archive_on_capture`` is on
        (a no-op otherwise -- the mailbox is never touched).

        Runs *after* the Odoo capture is committed (post-commit callback on
        a fresh cursor, the ``mail.mail`` pattern; inline under tests) and
        **never raises**: a failure must not lose the capture, so it is
        logged and surfaced to the user as a warning toast carrying the
        failure's own message.
        """
        if not transport or not transport.archive_on_capture:
            return False
        dbname = self.env.cr.dbname
        uid = self.env.uid
        context = dict(self.env.context)
        transport_id = transport.id

        def archive_and_report(env):
            try:
                env["conversation.transport"].browse(transport_id)._archive_remote(
                    external_id
                )
            except Exception as exc:  # noqa: BLE001 - see docstring
                _logger.warning(
                    "Auto-archive of %s on transport %s failed",
                    external_id,
                    transport_id,
                    exc_info=True,
                )
                message = (
                    exc.args[0]
                    if isinstance(exc, UserError) and exc.args
                    else str(exc) or exc.__class__.__name__
                )
                env["res.users"].sudo().browse(uid)._bus_send(
                    "simple_notification",
                    {
                        "type": "warning",
                        "sticky": True,
                        "title": _("The message was filed but not archived"),
                        "message": message,
                    },
                )

        if modules.module.current_test:
            archive_and_report(self.env)
            return True

        @self.env.cr.postcommit.add
        def archive_with_new_cursor():
            with Registry(dbname).cursor() as cr:
                archive_and_report(api.Environment(cr, uid, context))

        return True

    @api.model
    def action_route_via_alias(self, transport_id, external_id, model="mail.conversation"):
        """GTD 'route through an alias' action: feed the raw envelope for
        this inbox item into the ordinary mail gateway
        (``_route_via_alias``) so alias routing/threading/automation fire
        exactly as for a real inbound. Only meaningful for transports
        whose ``_fetch`` raw envelope carries the transport-native RFC822
        bytes (``raw['rfc822']`` -- true for the IMAP-family providers,
        conversation_imap/conversation_gmail); other transport shapes
        raise a clear error rather than silently doing nothing.

        :return: the id of the conversation the alias routed the message
            into (0/False if none matched/was created).
        """
        transport = self.env["conversation.transport"].browse(transport_id)
        raw = transport._fetch(external_id)
        rfc822 = raw.get("rfc822") if isinstance(raw, dict) else None
        if not rfc822:
            raise UserError(
                _(
                    "%(transport)s doesn't expose a raw message this "
                    "action can route through an alias.",
                    transport=transport.display_name,
                )
            )
        conversation = self._route_via_alias(rfc822, model=model)
        return conversation.id if conversation else False
