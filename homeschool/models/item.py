# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

PRIORITIES = [
    ("core", "Core"),
    ("reinvest", "Reinvestment"),
    ("enrichissement", "Enrichment"),
    ("differable", "Deferrable"),
]

COVERAGE_STATES = [
    ("not_started", "Not started"),
    ("planned", "Planned"),
    ("in_progress", "In progress"),
    ("evidenced", "Evidenced"),
]


class CurriculumItem(models.Model):
    _name = "homeschool.item"
    _description = "Curriculum item"
    _order = "csv_sequence, subject_id, code"
    _rec_name = "display_name"

    code = fields.Char(required=True, index=True, help="Stable id (PDA id or internal id), e.g. FLE-E-SYN-C-E.2.a.i.")
    csv_sequence = fields.Integer(default=100000, help="Row order in the family CSV (kept so exports stay diffable).")
    name = fields.Char(string="Label", required=True)
    kind = fields.Selection([("pda", "PDA"), ("internal", "Internal"), ("section", "Section node")], required=True, default="pda",
                            help="Section nodes are synthetic parents created for codes used as prefixes (covers, dependencies).")
    subject_id = fields.Many2one("homeschool.subject", required=True, ondelete="restrict")
    active = fields.Boolean(default=True)
    in_registry = fields.Boolean(default=True, help="False for PDA nodes known from deps-nodes.csv but not selected in the family registry (kept inactive so dependency edges resolve).")

    # PDA structure
    cycle = fields.Char()
    year_level = fields.Char(string="Year", help="'cycle', '5e', '6e', '5e-6e'…")
    competence = fields.Char()
    section = fields.Char()
    m1 = fields.Char(string="M1")
    m2 = fields.Char(string="M2")
    m3 = fields.Char(string="M3")
    m4 = fields.Char(string="M4")
    m5 = fields.Char(string="M5")
    m6 = fields.Char(string="M6")
    statut_3e = fields.Char(string="Status cycle 3")
    noyau = fields.Boolean(string="Core (noyau)")
    noyau_raw = fields.Char(help="The 'noyau' column verbatim (0/1/blank), kept for diffable exports.")
    parent_id = fields.Many2one("homeschool.item", ondelete="set null", index=True)
    child_ids = fields.One2many("homeschool.item", "parent_id")
    source_ref = fields.Char(help="Reference of the source document, verbatim (e.g. 'PDA-US-2009 p.8-9').")
    page = fields.Char()
    annee_cible = fields.Char(string="Target year")
    priorite = fields.Selection(PRIORITIES, string="Priority")
    note = fields.Text()
    project_codes = fields.Char(help="Raw 'projets' column from the CSV.")
    project_ids = fields.Many2many("homeschool.project", "homeschool_item_project_rel", "item_id", "project_id")

    # internal items
    domaine = fields.Char()
    exposition = fields.Char()
    projection = fields.Text()
    covers_ids = fields.Many2many(
        "homeschool.item", "homeschool_item_covers_rel", "internal_id", "covers_id",
        string="Covers (PDA items evidenced)",
    )
    covered_by_ids = fields.Many2many(
        "homeschool.item", "homeschool_item_covers_rel", "covers_id", "internal_id",
        string="Covered by (internal items)",
    )
    covers_basis = fields.Char()
    covers_refs = fields.Char(help="Document references this internal item covers (e.g. PA-1.3) — not items, kept as text.")

    # dependencies
    requires_ids = fields.One2many("homeschool.item.dependency", "to_item_id", string="Requires")
    required_by_ids = fields.One2many("homeschool.item.dependency", "from_item_id", string="Required by")

    # evidence
    trace_ids = fields.Many2many("homeschool.trace", "homeschool_trace_item_rel", "item_id", "trace_id", string="Traces")
    block_ids = fields.Many2many("homeschool.block", "homeschool_block_item_rel", "item_id", "block_id", string="Blocks")
    trace_count = fields.Integer(compute="_compute_coverage", store=True)
    block_count = fields.Integer(compute="_compute_coverage", store=True)
    last_evidence_date = fields.Date(compute="_compute_coverage", store=True)
    coverage_computed = fields.Selection(COVERAGE_STATES, compute="_compute_coverage", store=True)
    coverage_override = fields.Selection(COVERAGE_STATES, help="Manual status; wins over the computed one when set.")
    coverage_status = fields.Selection(COVERAGE_STATES, compute="_compute_coverage_status", store=True)
    coverage_note = fields.Char()
    coverage_date = fields.Date(help="Date of the last manual coverage update (from coverage.csv).")

    _code_unique = models.Constraint("unique(code)", "Curriculum item codes must be unique.")

    @api.depends("code", "name")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "%s — %s" % (rec.code, rec.name) if rec.name else rec.code

    @api.depends("trace_ids", "trace_ids.date", "block_ids", "block_ids.status", "block_ids.day_id.date")
    def _compute_coverage(self):
        today = fields.Date.context_today(self)
        for rec in self:
            traces = rec.trace_ids
            blocks = rec.block_ids
            rec.trace_count = len(traces)
            rec.block_count = len(blocks)
            dates = traces.mapped("date") + blocks.filtered(lambda b: b.status in ("done", "partial")).mapped("day_id.date")
            rec.last_evidence_date = max(dates) if dates else False
            if traces:
                rec.coverage_computed = "evidenced"
            elif blocks.filtered(lambda b: b.status in ("done", "partial")):
                rec.coverage_computed = "in_progress"
            elif blocks.filtered(lambda b: b.status == "planned" and b.day_id.date and b.day_id.date >= today):
                rec.coverage_computed = "planned"
            elif blocks:
                rec.coverage_computed = "planned"
            else:
                rec.coverage_computed = "not_started"

    @api.depends("coverage_computed", "coverage_override")
    def _compute_coverage_status(self):
        for rec in self:
            rec.coverage_status = rec.coverage_override or rec.coverage_computed or "not_started"

    @api.constrains("parent_id")
    def _check_parent_cycle(self):
        if self._has_cycle():
            raise ValidationError(self.env._("An item cannot be its own ancestor."))

    @api.model
    def _by_code(self, code):
        return self.with_context(active_test=False).search([("code", "=", code)], limit=1)

    @api.model
    def _resolve(self, code, subject=None):
        """An item by exact code, or — when the code is a prefix of existing codes (a section
        such as 'ELA-REL-A' or 'MATH-OPE-A.6') — a synthetic section node created on the fly
        and made the parent of the parent-less items under that prefix. Empty when nothing
        matches."""
        code = (code or "").strip()
        if not code:
            return self.browse()
        item = self._by_code(code)
        if item:
            return item
        children = self.with_context(active_test=False).search(["|", ("code", "=like", code + ".%"), ("code", "=like", code + "-%")])
        if not children:
            return self.browse()
        first = children.sorted("csv_sequence")[0]
        node = self.create({
            "code": code, "name": code, "kind": "section", "subject_id": (subject or first.subject_id).id,
            "csv_sequence": first.csv_sequence, "source_ref": first.source_ref,
        })
        children.filtered(lambda c: not c.parent_id).write({"parent_id": node.id})
        return node

    def _descendants(self):
        """The item and every descendant (section nodes apply to all of them)."""
        result = self.browse()
        todo = self
        while todo:
            result |= todo
            todo = todo.mapped("child_ids") - result
        return result


class ItemDependency(models.Model):
    _name = "homeschool.item.dependency"
    _description = "Prerequisite edge between curriculum items"
    _order = "from_item_id, to_item_id"

    from_item_id = fields.Many2one("homeschool.item", required=True, ondelete="cascade", string="Comes first")
    to_item_id = fields.Many2one("homeschool.item", required=True, ondelete="cascade", string="Then")
    basis = fields.Char(help="Provenance tag of the edge ([P], [C]…).")
    mode = fields.Char()
    note = fields.Char()

    _edge_unique = models.Constraint(
        "unique(from_item_id, to_item_id)", "This prerequisite edge already exists."
    )

    @api.constrains("from_item_id", "to_item_id")
    def _check_not_self(self):
        for rec in self:
            if rec.from_item_id == rec.to_item_id:
                raise ValidationError(self.env._("An item cannot require itself."))
