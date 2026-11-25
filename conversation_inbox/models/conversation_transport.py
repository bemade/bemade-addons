from datetime import datetime, timezone

from odoo import api, models


def _naive_utc(value):
    """An aware datetime as the same instant in naive UTC; anything else
    (False, a string, an already-naive datetime) unchanged.

    The JSON-RPC serializer writes a datetime's own wall clock without
    converting it, so a message dated ``18:10 -0500`` would reach the
    browser as ``18:10`` and be read as UTC. The web client treats every
    serialized datetime as UTC, so hand it UTC.
    """
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


class ConversationTransport(models.Model):
    _inherit = "conversation.transport"

    @api.model
    def browse_page(self, transport_id, query=None, page=1):
        result = super().browse_page(transport_id, query=query, page=page)
        if not isinstance(result, dict):
            return result
        # Copy the stubs: the engine keeps them in a shared cache.
        items = [
            dict(item, date=_naive_utc(item.get("date")))
            if isinstance(item, dict) and "date" in item
            else item
            for item in result.get("items") or []
        ]
        return dict(result, items=items)

    def _action_after_remove(self):
        """After removing a mailbox, land back on the "My mailboxes" list
        (a removed mailbox is gone from it), not on the dead form."""
        action = self.env["ir.actions.actions"]._for_xml_id(
            "conversation_inbox.conversation_transport_action_my"
        )
        action["target"] = "main"
        return action
