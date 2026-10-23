from odoo import models


class ConversationTransport(models.Model):
    _inherit = "conversation.transport"

    def _draft_prefills_user_signature(self):
        """Whether a new reply draft sent from this transport starts with the
        acting user's own signature.

        True for every transport by default. A transport that speaks for a
        team rather than a person (a team mailbox) opts out from the module
        that introduces it, so this module needs no knowledge of it.
        """
        self.ensure_one()
        return True
