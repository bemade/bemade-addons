# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain
from odoo.tools import SQL

from .item_coverage import COVERAGE_STATES

PRIORITIES = [
    ("core", "Core"),
    ("reinvest", "Reinvestment"),
    ("enrichissement", "Enrichment"),
    ("differable", "Deferrable"),
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

    # evidence (all families; the item is shared)
    trace_ids = fields.Many2many("homeschool.trace", "homeschool_trace_item_rel", "item_id", "trace_id", string="Traces")
    block_ids = fields.Many2many("homeschool.block", "homeschool_block_item_rel", "item_id", "block_id", string="Blocks")

    # coverage, per family: one homeschool.item.coverage row per (item, company); the fields
    # below are the CURRENT company's row (not stored; an item without a row is not started)
    coverage_ids = fields.One2many("homeschool.item.coverage", "item_id", string="Coverage by family")
    trace_count = fields.Integer(compute="_compute_coverage")
    block_count = fields.Integer(compute="_compute_coverage")
    last_evidence_date = fields.Date(compute="_compute_coverage")
    coverage_computed = fields.Selection(COVERAGE_STATES, compute="_compute_coverage")
    coverage_status = fields.Selection(COVERAGE_STATES, compute="_compute_coverage", search="_search_coverage_status")
    # the manual fields: one compute + inverse each, so that writing one of them leaves the
    # status fields free to be invalidated (a field is protected together with its co-computed fields)
    coverage_override = fields.Selection(COVERAGE_STATES, compute="_compute_coverage_override", inverse="_inverse_coverage_override",
                                         readonly=False, help="Manual status of the current family; wins over the computed one when set.")
    coverage_note = fields.Char(compute="_compute_coverage_note", inverse="_inverse_coverage_note", readonly=False)
    coverage_date = fields.Date(compute="_compute_coverage_date", inverse="_inverse_coverage_date", readonly=False,
                                help="Date of the last manual coverage update of the current family (from coverage.csv).")

    _code_unique = models.Constraint("unique(code)", "Curriculum item codes must be unique.")

    @api.depends("code", "name")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "%s — %s" % (rec.code, rec.name) if rec.name else rec.code

    # ------------------------------------------------------------------
    # coverage of the current family
    # ------------------------------------------------------------------
    def _coverage_for(self, company=None, create=False):
        """The coverage rows of these items for ``company`` (default: the current company):
        at most one per item. With ``create`` the missing rows are created — only do that to
        store a manual status; evidence creates its rows itself."""
        company = company or self.env.company
        Coverage = self.env["homeschool.item.coverage"]
        rows = Coverage.search([("item_id", "in", self.ids), ("company_id", "=", company.id)])
        if create:
            missing = self - rows.item_id
            if missing:
                rows |= Coverage.create([{"item_id": item.id, "company_id": company.id} for item in missing])
        return rows

    def _current_coverage(self):
        """The current company's row of each item (empty when the family has none)."""
        company = self.env.company
        return {rec.id: rec.coverage_ids.filtered(lambda c: c.company_id == company)[:1] for rec in self}

    @api.depends_context("company")
    @api.depends("coverage_ids.company_id", "coverage_ids.status", "coverage_ids.status_computed",
                 "coverage_ids.trace_count", "coverage_ids.block_count", "coverage_ids.last_evidence_date")
    def _compute_coverage(self):
        rows = self._current_coverage()
        for rec in self:
            row = rows[rec.id]
            rec.trace_count = row.trace_count
            rec.block_count = row.block_count
            rec.last_evidence_date = row.last_evidence_date
            rec.coverage_computed = row.status_computed or "not_started"
            rec.coverage_status = row.status or "not_started"

    def _compute_coverage_manual(self, fname, row_fname):
        rows = self._current_coverage()
        for rec in self:
            rec[fname] = rows[rec.id][row_fname]

    def _inverse_coverage_manual(self, fname, row_fname):
        for rec in self:
            value = rec[fname] or False
            row = rec._coverage_for(create=bool(value))
            if row:
                row.write({row_fname: value})

    @api.depends_context("company")
    @api.depends("coverage_ids.company_id", "coverage_ids.override")
    def _compute_coverage_override(self):
        self._compute_coverage_manual("coverage_override", "override")

    def _inverse_coverage_override(self):
        self._inverse_coverage_manual("coverage_override", "override")

    @api.depends_context("company")
    @api.depends("coverage_ids.company_id", "coverage_ids.note")
    def _compute_coverage_note(self):
        self._compute_coverage_manual("coverage_note", "note")

    def _inverse_coverage_note(self):
        self._inverse_coverage_manual("coverage_note", "note")

    @api.depends_context("company")
    @api.depends("coverage_ids.company_id", "coverage_ids.date")
    def _compute_coverage_date(self):
        self._compute_coverage_manual("coverage_date", "date")

    def _inverse_coverage_date(self):
        self._inverse_coverage_manual("coverage_date", "date")

    def _search_coverage_status(self, operator, value):
        if operator != "in":
            return NotImplemented  # the ORM comes back with the positive operator and negates
        values = set(value)
        company_id = self.env.company.id
        domain = Domain("coverage_ids", "any", Domain("company_id", "=", company_id) & Domain("status", "in", list(values - {False})))
        if "not_started" in values or False in values:
            # an item without a row for this family is not started
            domain |= Domain("coverage_ids", "not any", Domain("company_id", "=", company_id))
        return domain

    def _read_group_groupby(self, alias, groupby_spec, query):
        """Group by ``coverage_status`` = the current family's row (not started without one)."""
        if groupby_spec != "coverage_status":
            return super()._read_group_groupby(alias, groupby_spec, query)
        self._check_field_access(self._fields["coverage_status"], "read")
        Coverage = self.env["homeschool.item.coverage"]
        Coverage.flush_model(["item_id", "company_id", "status"])
        return SQL(
            "COALESCE((SELECT c.status FROM %s c WHERE c.item_id = %s AND c.company_id = %s), 'not_started')",
            SQL.identifier(Coverage._table), SQL.identifier(alias, "id"), self.env.company.id,
        )

    def write(self, vals):
        result = super().write(vals)
        if "trace_ids" in vals or "block_ids" in vals:
            Coverage = self.env["homeschool.item.coverage"]
            for rec in self:
                for company in rec.trace_ids.company_id | rec.block_ids.company_id:
                    Coverage._ensure_rows(rec, company)
        return result

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
