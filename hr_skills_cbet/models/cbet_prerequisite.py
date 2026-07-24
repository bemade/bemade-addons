from odoo import api, fields, models
from odoo.exceptions import ValidationError


class CbetPrerequisite(models.Model):
    """UC-CAT-03 — typed prerequisite edge between two competencies."""

    _name = "cbet.prerequisite"
    _description = "CBET Competency Prerequisite"

    competency_id = fields.Many2one(
        "cbet.competency", required=True, ondelete="cascade", index=True,
    )
    prerequisite_id = fields.Many2one(
        "cbet.competency", string="Prerequisite", required=True, ondelete="cascade",
    )
    prereq_type = fields.Selection(
        [("obligatoire", "Obligatoire"), ("recommande", "Recommandé")],
        required=True,
        default="obligatoire",
    )

    _edge_uniq = models.Constraint(
        "unique(competency_id, prerequisite_id)",
        "This prerequisite edge already exists.",
    )

    @api.constrains("competency_id", "prerequisite_id")
    def _check_no_cycle(self):
        for edge in self:
            # UC-CAT-03 AC3 — self-prerequisite blocked.
            if edge.competency_id == edge.prerequisite_id:
                raise ValidationError(
                    self.env._("A competency cannot be its own prerequisite."))
            # UC-CAT-03 AC2 — direct + transitive cycle blocked. A cycle exists
            # iff competency_id is reachable from prerequisite_id via any edge.
            reachable = edge.prerequisite_id
            todo = edge.prerequisite_id
            seen = self.env["cbet.competency"]
            while todo:
                seen |= todo
                nxt = todo.mapped("prerequisite_ids.prerequisite_id")
                reachable |= nxt
                todo = nxt - seen
            if edge.competency_id in reachable:
                raise ValidationError(
                    self.env._(
                        "This prerequisite would create a cycle: %(prereq)s already "
                        "depends (transitively) on %(comp)s.",
                        prereq=edge.prerequisite_id.code,
                        comp=edge.competency_id.code,
                    ))
