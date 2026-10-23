from odoo import models


class ConversationTransport(models.Model):
    _inherit = "conversation.transport"

    def _draft_prefills_user_signature(self):
        """A team mailbox speaks for the team, not for whoever answers: a new
        reply draft sent from it does not start with the user's own
        signature."""
        self.ensure_one()
        if self.provider == "team_smtp":
            return False
        return super()._draft_prefills_user_signature()
