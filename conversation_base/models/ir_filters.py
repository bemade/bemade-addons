# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

from odoo import api, models
from odoo.tools.translate import LazyTranslate

_lt = LazyTranslate(__name__)

# ``ir.filters.name`` is a plain, non-translatable Char, so the four shared
# saved filters shipped by this module would show in English to every user.
# Their names are therefore translated when the filters are served to the
# search view, keyed on the shipped records and on the shipped English name.
# The translation keys carry a "(saved filter)" qualifier because the bare
# words ("Unread", "Unanswered") are already translated, differently, as field
# labels of this module and share one code-translation namespace with them.
SHIPPED_FILTER_NAMES = {
    "conversation_base.ir_filter_conversation_unread": _lt("Unread (saved filter)"),
    "conversation_base.ir_filter_conversation_unanswered": _lt(
        "Unanswered (saved filter)"
    ),
    "conversation_base.ir_filter_conversation_oldest_unanswered": _lt(
        "Oldest unanswered first (saved filter)"
    ),
    "conversation_base.ir_filter_conversation_mine": _lt("Mine (saved filter)"),
}
QUALIFIER = " (saved filter)"


class IrFilters(models.Model):
    _inherit = "ir.filters"

    @api.model
    def get_filters(self, model, *args, **kwargs):
        """Serve the shipped Conversations filters with a name in the user's language.

        Default-inert: any other model, any other filter, and a shipped filter
        whose name was edited, are returned exactly as the core method does.
        """
        filters = super().get_filters(model, *args, **kwargs)
        if model != "mail.conversation":
            return filters
        lang = self.env["res.users"].context_get().get("lang")
        translate_env = self.with_context(lang=lang).env
        translated = {}
        for xmlid, label in SHIPPED_FILTER_NAMES.items():
            record = self.env.ref(xmlid, raise_if_not_found=False)
            if record:
                name = translate_env._(label)
                if name != label._source:
                    translated[record.id] = (label._source.removesuffix(QUALIFIER), name)
        for filter_data in filters:
            source_name, name = translated.get(filter_data["id"], (None, None))
            # A filter renamed by an admin keeps its stored name; so does a
            # language without a catalogue entry (the key is not a name).
            if source_name == filter_data["name"]:
                filter_data["name"] = name
        return filters
