from odoo import models


class MailConversation(models.Model):
    _inherit = "mail.conversation"

    def action_open_thread_view(self):
        """Open the conversation laid out as an email thread, in the main
        window. An optional prototype: the form stays the default and nothing
        is written by switching views."""
        self.ensure_one()
        self.check_access("read")
        return {
            "type": "ir.actions.client",
            "tag": "conversation_thread_view",
            "name": self.env._("Thread view"),
            "target": "current",
            "context": {"active_id": self.id},
        }

    def thread_view_summary(self):
        """What the thread view shows above the messages. Read-only."""
        self.ensure_one()
        self.check_access("read")
        state_labels = dict(
            self._fields["state"]._description_selection(self.env)
        )
        return {
            "id": self.id,
            "name": self.name,
            "state": self.state,
            "state_label": state_labels.get(self.state, self.state),
            "user": self.user_id.display_name or False,
            "team": self.team_id.display_name or False,
            "tags": [
                {"id": tag.id, "name": tag.name, "color": tag.color}
                for tag in self.tag_ids
            ],
        }
