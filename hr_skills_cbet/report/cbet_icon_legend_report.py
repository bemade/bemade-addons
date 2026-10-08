from odoo import api, models

from ..models.cbet_icon import ICON_CATEGORIES


class CbetIconLegendReport(models.AbstractModel):
    """The job-aid icon legend: the catalog grouped by category.

    Printed from the Icons list it covers the selection; printed from the
    menu (no record) it covers the whole active catalog.
    """

    _name = "report.hr_skills_cbet.report_cbet_icon_legend"
    _description = "CBET job-aid icon legend report"

    @api.model
    def _get_report_values(self, docids, data=None):
        Icon = self.env["cbet.icon"]
        icons = Icon.browse(docids).exists() if docids else Icon.search([])
        icons = icons.sorted(lambda i: (i.category or "~", i.token))
        labels = dict(Icon._fields["category"]._description_selection(self.env))
        groups = []
        for code, _label in ICON_CATEGORIES:
            sub = icons.filtered(lambda i: i.category == code)
            if sub:
                groups.append({"code": code, "label": labels.get(code, code), "icons": sub})
        other = icons.filtered(lambda i: not i.category)
        if other:
            groups.append({"code": False, "label": self.env._("Other"), "icons": other})
        return {
            "doc_ids": icons.ids,
            "doc_model": "cbet.icon",
            "docs": icons,
            "groups": groups,
        }
