from odoo import models


class ConversationTransport(models.Model):
    _inherit = "conversation.transport"

    def _action_after_remove(self):
        """After removing a mailbox, land back on the "My mailboxes" list
        (a removed mailbox is gone from it), not on the dead form."""
        action = self.env["ir.actions.actions"]._for_xml_id(
            "conversation_inbox.conversation_transport_action_my"
        )
        action["target"] = "main"
        return action
