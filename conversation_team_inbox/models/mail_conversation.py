from odoo import api, models


class MailConversation(models.Model):
    _inherit = "mail.conversation"

    @api.model
    def _find_captured(self, transport, external_id, message_id=None):
        """Also recognise a message by its RFC822 ``message_id``.

        A message delivered through a team alias carries no transport
        ``external_id`` (no IMAP UID), so keying on that alone lets the same
        mail be filed a second time from the inbox viewer. When the caller
        knows the Message-Id, fall back to it. Not tied to ``transport``:
        the whole point is that the first copy did not come through it.
        """
        conversation = self.browse()
        if external_id:
            conversation = super()._find_captured(transport, external_id)
        if conversation or not message_id:
            return conversation
        bare = message_id.strip().strip("<>")
        if not bare:
            return conversation
        message = self.env["mail.message"].search(
            [
                ("model", "=", self._name),
                ("message_id", "in", [bare, f"<{bare}>"]),
            ],
            limit=1,
        )
        return self.browse(message.res_id) if message.res_id else conversation

    @api.model
    def _capture_stub(self, transport, stub, mode="new", target=None):
        """Idempotent on the stub's Message-Id: a mail that already reached
        a conversation (through a team alias, or an earlier capture) is not
        filed again."""
        message_id = stub.get("message_id")
        existing = (
            self._find_captured(transport, None, message_id=message_id)
            if message_id
            else self.browse()
        )
        if existing and (mode in ("new", "link") or existing == target):
            if mode == "link" and target:
                self._ensure_link(existing, target)
            return existing
        return super()._capture_stub(transport, stub, mode=mode, target=target)

    @api.model
    def _ensure_link(self, conversation, record):
        Link = self.env["mail.conversation.link"]
        domain = [
            ("conversation_id", "=", conversation.id),
            ("res_model", "=", record._name),
            ("res_id", "=", record.id),
        ]
        if not Link.search_count(domain):
            Link.create(
                {
                    "conversation_id": conversation.id,
                    "res_model": record._name,
                    "res_id": record.id,
                    "reason": "manual",
                }
            )
