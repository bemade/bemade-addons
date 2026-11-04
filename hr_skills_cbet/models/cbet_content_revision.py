from odoo import api, fields, models
from odoo.tools.mail import html_sanitize

REVISIONS_PER_FIELD = 50


class CbetContentRevision(models.Model):
    """UC-CAT-08 — the previous html of a document body, kept when the body
    changes, so an author can go back.

    One row per (document field, language) per write; the last
    ``REVISIONS_PER_FIELD`` are kept. The module's own mechanism rather than
    ``html.field.history.mixin``: the core mixin refuses ``sanitize=False``
    fields, and the bodies are whole documents per language on purpose (see
    ``test_cat_17``). A revision is bound to the language it was written in,
    so restoring one touches that language only.
    """

    _name = "cbet.content.revision"
    _description = "CBET Content Revision"
    _order = "id desc"
    _rec_name = "field_label"

    competency_id = fields.Many2one(
        "cbet.competency", required=True, ondelete="cascade", index=True,
    )
    section_id = fields.Many2one(
        "cbet.job.aid.section", string="Job aid section", ondelete="cascade", index=True,
        help="Set when the revision is a job-aid section note; empty for a "
             "competency body.",
    )
    field_name = fields.Char(required=True, readonly=True)
    field_label = fields.Char(compute="_compute_field_label")
    lang = fields.Char(string="Language", required=True, readonly=True)
    lang_name = fields.Char(compute="_compute_lang_name", string="Language name")
    previous_html = fields.Html(
        string="Previous content", sanitize=False, readonly=True, prefetch=False,
    )
    user_id = fields.Many2one(
        "res.users", string="Changed by", readonly=True, default=lambda self: self.env.user,
    )
    date = fields.Datetime(readonly=True, default=fields.Datetime.now)

    @api.depends("field_name", "section_id", "section_id.name", "section_id.job_aid_id.name")
    def _compute_field_label(self):
        for rev in self:
            model = rev.section_id._name if rev.section_id else "cbet.competency"
            field = self.env[model]._fields.get(rev.field_name)
            label = field._description_string(self.env) if field else rev.field_name
            if rev.section_id:
                label = "%s — %s › %s" % (
                    rev.section_id.job_aid_id.name, rev.section_id.name or "", label)
            rev.field_label = label

    @api.depends("lang")
    def _compute_lang_name(self):
        names = dict(self.env["res.lang"].get_installed())
        for rev in self:
            rev.lang_name = names.get(rev.lang, rev.lang)

    def _target(self):
        self.ensure_one()
        return self.section_id or self.competency_id

    def action_restore(self):
        """Write the stored html back on the document, in the revision's
        language only. The current content becomes a revision in turn, so a
        restore can be undone. Runs as the user: the trainer guard applies."""
        for rev in self:
            rev._target().with_context(lang=rev.lang).write({rev.field_name: rev.previous_html})
        return True

    @api.model
    def _prune(self, keys):
        """Keep the newest ``REVISIONS_PER_FIELD`` rows of each
        (competency, section, field, lang) in ``keys``."""
        for competency_id, section_id, field_name, lang in keys:
            stale = self.sudo().search([
                ("competency_id", "=", competency_id),
                ("section_id", "=", section_id or False),
                ("field_name", "=", field_name),
                ("lang", "=", lang),
            ], offset=REVISIONS_PER_FIELD)
            if stale:
                stale.unlink()


class CbetContentRevisionMixin(models.AbstractModel):
    """Records a ``cbet.content.revision`` for every change to the fields in
    ``_revision_fields`` — through ``write`` (the language of the context)
    and through the editor's translation dialog (``update_field_translations``,
    per language)."""

    _name = "cbet.content.revision.mixin"
    _description = "CBET Content Revision Mixin"
    _revision_fields = ()

    @staticmethod
    def _sanitize_body(value):
        """The document bodies are ``sanitize=False`` fields (one whole document
        per language), so Odoo does not clean them itself. Trainers write them
        from the editor and the translate dialog, so everything is passed
        through the same sanitizer the importer uses — scripts, event handlers
        and forms never reach the stored html that Managers render raw."""
        if not value or not isinstance(value, str):
            return value
        return html_sanitize(
            value, silent=True, sanitize_tags=True, sanitize_attributes=True,
            sanitize_style=False, sanitize_form=True, strip_style=False, strip_classes=False)

    def _revision_link_vals(self):
        """The ``cbet.content.revision`` columns binding a revision to self."""
        self.ensure_one()
        raise NotImplementedError

    def _cbet_check_content_write(self, vals):
        """Hook for the authoring guard (no-op here)."""

    def _stored_before(self, field_names, langs):
        """{record id: {field: {lang: previous html}}} from the stored
        translations — a language that only *fell back* on the English has no
        document of its own, so nothing to restore ("" there)."""
        before = {}
        for rec in self:
            before[rec.id] = {}
            for fname in field_names:
                stored = self._fields[fname]._get_stored_translations(rec) or {}
                before[rec.id][fname] = {lang: stored.get(lang) or "" for lang in langs}
        return before

    def _record_revisions(self, before):
        """``before``: {record id: {field: {lang: previous html}}}. Creates a
        revision for every (field, lang) whose content changed to something
        else and was not empty before (an empty document is nothing to
        restore)."""
        rows, keys = [], set()
        for rec in self:
            link = rec._revision_link_vals()
            for field_name, per_lang in before.get(rec.id, {}).items():
                for lang, old in per_lang.items():
                    new = rec.with_context(lang=lang)[field_name] or ""
                    if not old or new == old:
                        continue
                    rows.append(dict(link, field_name=field_name, lang=lang, previous_html=old,
                                     user_id=self.env.uid))
                    keys.add((link["competency_id"], link.get("section_id"), field_name, lang))
        if rows:
            Revision = self.env["cbet.content.revision"].sudo()
            Revision.create(rows)
            Revision._prune(keys)

    def write(self, vals):
        self._cbet_check_content_write(vals)
        changed = [f for f in self._revision_fields if f in vals]
        if changed:
            vals = dict(vals, **{f: self._sanitize_body(vals[f]) for f in changed})
        before = self._stored_before(changed, [self.env.lang or "en_US"]) if changed else {}
        res = super().write(vals)
        if before:
            self._record_revisions(before)
        return res

    def _update_field_translations(self, field_name, translations, digest=None, source_lang=""):
        self._cbet_check_content_write({field_name: True})
        before = {}
        if field_name in self._revision_fields and translations:
            translations = {lang: self._sanitize_body(v) for lang, v in translations.items()}
            before = self._stored_before([field_name], list(translations))
        res = super()._update_field_translations(
            field_name, translations, digest=digest, source_lang=source_lang)
        if before:
            self._record_revisions(before)
        return res
