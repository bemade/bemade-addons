from odoo import models
from odoo.fields import Domain
from odoo.exceptions import AccessError


class ConversationDraftAccessMixin(models.AbstractModel):
    """Delegate record access to a parent record, the way ``mail.activity``
    defers to the document it is attached to.

    A model using this mixin names the many2one it delegates through in
    ``_delegated_access_field``. A record may be read when its parent may be
    read, and written (created, unlinked) when its parent may be written.
    Nothing is keyed on ``create_uid``: when a draft is handed to a
    colleague, access follows the conversation, not the author.
    """

    _name = "conversation.draft.access.mixin"
    _description = "Conversation Draft Access Delegation"

    _delegated_access_field = None

    def _check_access(self, operation):
        result = super()._check_access(operation)
        if not self or not self._delegated_access_field:
            return result
        parent_operation = "read" if operation == "read" else "write"
        parents = self.sudo().mapped(self._delegated_access_field).with_env(self.env)
        allowed = parents._filtered_access(parent_operation)
        forbidden = self.filtered(
            lambda record: record.sudo()[self._delegated_access_field] not in allowed
        )
        if not forbidden:
            return result

        def make_error(forbidden=forbidden):
            return AccessError(
                self.env._(
                    "Access to this reply draft is refused (%(operation)s): it "
                    "follows access to the conversation it belongs to.",
                    operation=operation,
                )
            )

        if result:
            return (result[0] + forbidden, result[1])
        return (forbidden, make_error)

    def _search(
        self, domain, offset=0, limit=None, order=None, *, bypass_access=False, **kwargs
    ):
        if self._delegated_access_field and not (
            self.env.is_superuser() or bypass_access
        ):
            parent_model = self._fields[self._delegated_access_field].comodel_name
            domain = Domain(domain) & Domain(
                self._delegated_access_field,
                "in",
                self.env[parent_model]._search([]),
            )
        return super()._search(
            domain, offset, limit, order, bypass_access=bypass_access, **kwargs
        )
