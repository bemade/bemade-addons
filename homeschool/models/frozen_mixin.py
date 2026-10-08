# -*- coding: utf-8 -*-
"""Past-day freeze: the texts of a past record are corrected, never rewritten.

Models declare ``_frozen_fields = ("went_well", "went_badly")`` and must carry a
``date`` field and a ``corrections`` Text field. From the next day on, a write of a
frozen field appends a dated line to ``corrections`` (``- **<today>** (<label>): <text>``)
and leaves the field itself untouched; everything else in the same write lands as usual.
``journal_force_edit`` in the context bypasses the freeze (imports, repairs: the file is
the truth).
"""
from odoo import fields, models


class FrozenMixin(models.AbstractModel):
    _name = "homeschool.frozen.mixin"
    _description = "Past-day freeze mixin"

    _frozen_fields = ()

    def _is_past(self):
        self.ensure_one()
        return bool(self.date and self.date < fields.Date.context_today(self))

    def write(self, vals):
        """Editing a frozen field of a past record appends a dated correction instead."""
        frozen = {k: v for k, v in vals.items() if k in self._frozen_fields}
        if not frozen or self.env.context.get("journal_force_edit"):
            return super().write(vals)
        rest = {k: v for k, v in vals.items() if k not in self._frozen_fields}
        today = fields.Date.to_string(fields.Date.context_today(self))
        # the label in the writer's language — the web client sends it, an API call usually not
        lang_env = self.env if self.env.lang else self.with_context(lang=self.env.user.lang).env
        for rec in self:
            if rec._is_past():
                lines = [rec.corrections or ""]
                for field_name, value in frozen.items():
                    label = self._fields[field_name]._description_string(lang_env)
                    lines.append("- **%s** (%s): %s" % (today, label, value or ""))
                super(FrozenMixin, rec).write(dict(rest, corrections="\n".join(lines).strip()))
            else:
                super(FrozenMixin, rec).write(dict(rest, **frozen))
        return True

    def append_note(self, field_name, text):
        """Append a bullet to a Markdown field (today) or to the corrections (past)."""
        self.ensure_one()
        if self._is_past():
            return self.write({field_name: text})
        current = self[field_name] or ""
        return self.write({field_name: (current + "\n" if current else "") + text})
