# -*- coding: utf-8 -*-
"""Past-day freeze: the texts of a past record are corrected, never rewritten.

Models declare ``_frozen_fields = ("went_well", "went_badly")`` and must carry a
``date`` field and a ``corrections`` Text field. From the next day on, a write that
changes the text of a frozen field appends a dated line to ``corrections``
(``- **<today>** (<label>): <text>``) and leaves the field itself untouched; a frozen field
still empty takes its first text in place (closing a day late: nothing to correct), and an
empty value over an empty field is a no-op. Everything else in the same write lands as usual.
The label is in the student's language (the record's ``student_id``), else the writer's.
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
        # fallback label language: the writer's — the web client sends it, an API call usually not
        lang_env = self.env if self.env.lang else self.with_context(lang=self.env.user.lang).env
        for rec in self:
            if rec._is_past():
                label_env = rec._correction_label_env(lang_env)
                in_place, lines = {}, []
                for field_name, value in frozen.items():
                    if not (rec[field_name] or "").strip():
                        # still empty: the first text goes in the field (an empty one: nothing)
                        if (value or "").strip():
                            in_place[field_name] = value
                        continue
                    label = self._fields[field_name]._description_string(label_env)
                    lines.append("- **%s** (%s): %s" % (today, label, value or ""))
                vals_rec = dict(rest, **in_place)
                if lines:
                    vals_rec["corrections"] = "\n".join([rec.corrections or ""] + lines).strip()
                if vals_rec:
                    super(FrozenMixin, rec).write(vals_rec)
            else:
                super(FrozenMixin, rec).write(dict(rest, **frozen))
        return True

    def _correction_label_env(self, fallback_env):
        """The environment whose language names the fields in a correction line: the
        student's (the journal is his record, written in his language), else
        ``fallback_env`` (the writer's)."""
        self.ensure_one()
        lang = "student_id" in self._fields and self.student_id.partner_id.lang
        return self.with_context(lang=lang).env if lang else fallback_env

    def append_note(self, field_name, text):
        """Append a bullet to a Markdown field (today, or a past record's empty field) or to
        the corrections (a past record's field already written)."""
        self.ensure_one()
        if self._is_past():
            return self.write({field_name: text})
        current = self[field_name] or ""
        return self.write({field_name: (current + "\n" if current else "") + text})
