from markupsafe import Markup, escape

from odoo import api, fields, models


class CbetPublishWizard(models.TransientModel):
    """UC-CAT-08 AC5 — the publish confirmation: the version about to be
    frozen and, after a first publication, which documents changed since the
    last version (counts only)."""

    _name = "cbet.publish.wizard"
    _description = "Publish a competency"

    competency_id = fields.Many2one("cbet.competency", required=True, ondelete="cascade")
    current_version = fields.Char(related="competency_id.version")
    next_version = fields.Char(compute="_compute_changes")
    first_publication = fields.Boolean(compute="_compute_changes")
    changes_html = fields.Html(compute="_compute_changes", sanitize=False)

    @api.depends("competency_id")
    def _compute_changes(self):
        _ = self.env._
        for wizard in self:
            comp = wizard.competency_id
            wizard.next_version = comp._bump_version() if comp else False
            changes = comp._document_changes() if comp else None
            wizard.first_publication = changes is None
            if changes is None:
                wizard.changes_html = Markup("<p>%s</p>") % _(
                    "First publication: every document is frozen as version %s.",
                    wizard.next_version)
                continue
            rows = []
            for change in changes:
                if change["changed"]:
                    status = Markup('<span class="text-warning fw-bold">%s</span>') % _(
                        "%(changed)s of %(total)s changed",
                        changed=change["changed"], total=change["total"])
                else:
                    status = Markup('<span class="text-muted">%s</span>') % _("unchanged")
                rows.append(Markup("<li>%s: %s</li>") % (escape(change["label"]), status))
            if not any(c["changed"] for c in changes):
                intro = _("Nothing changed since version %s.", comp.version)
            else:
                intro = _("Changed since version %s:", comp.version)
            wizard.changes_html = Markup("<p>%s</p><ul>%s</ul>") % (intro, Markup("").join(rows))

    def action_confirm(self):
        self.ensure_one()
        self.competency_id.action_publish()
        return {"type": "ir.actions.act_window_close"}
