from odoo import api, fields, models

# Rows rendered in the record tab; the count still reflects every link.
RECORD_TAB_LIMIT = 100


class MailConversationLink(models.Model):
    _inherit = "mail.conversation.link"

    @api.model
    def get_record_conversations(self, res_model, res_id):
        """Payload of the "Relevant Conversations" tab of a record.

        Called by the chatter, once per record load. Internal users only;
        anyone else gets an empty payload rather than an access error.
        """
        empty = {"count": 0, "scopes": []}
        if not (res_model and res_id) or not self.env.user.has_group(
            "base.group_user"
        ):
            return empty
        scopes = [
            scope
            for scope in self._record_conversation_scopes(res_model, res_id)
            if scope["conversations"]
        ]
        if not scopes:
            return empty
        return {
            "count": sum(scope.get("count", len(scope["conversations"])) for scope in scopes),
            "scopes": scopes,
        }

    @api.model
    def _record_conversation_scopes(self, res_model, res_id):
        """Scopes shown in the tab, in display order.

        Each scope is ``{"key", "label", "count", "conversations"}`` and each
        conversation row may carry a ``via`` string saying why it is shown.
        Extend by calling super and appending a scope.
        """
        conversations = self.env["mail.conversation"].search(
            [
                (
                    "link_ids",
                    "any",
                    [("res_model", "=", res_model), ("res_id", "=", res_id)],
                )
            ],
            order="last_message_date desc nulls last, id desc",
            limit=RECORD_TAB_LIMIT,
        )
        if not conversations:
            return []
        total = len(conversations)
        if total == RECORD_TAB_LIMIT:
            total = self.env["mail.conversation"].search_count(
                [
                    (
                        "link_ids",
                        "any",
                        [("res_model", "=", res_model), ("res_id", "=", res_id)],
                    )
                ]
            )
        return [
            {
                "key": "linked",
                "label": self.env._("Linked directly"),
                "count": total,
                "conversations": self._record_conversation_rows(conversations),
            }
        ]

    @api.model
    def _record_conversation_rows(self, conversations):
        states = dict(
            conversations._fields["state"]._description_selection(self.env)
        )
        return [
            {
                "id": conversation.id,
                "name": conversation.name,
                "state": conversation.state,
                "state_label": states.get(conversation.state, conversation.state),
                "user_name": conversation.user_id.name or False,
                "last_message_date": fields.Datetime.to_string(
                    conversation.last_message_date
                )
                or False,
            }
            for conversation in conversations
        ]
