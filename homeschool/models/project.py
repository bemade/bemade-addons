# -*- coding: utf-8 -*-
from odoo import api, fields, models

from .markdown_mixin import markdown_html_field


class Project(models.Model):
    _name = "homeschool.project"
    _description = "Project or mini-project carrying curriculum content"
    _inherit = ["mail.thread", "homeschool.markdown.mixin"]
    _order = "state, sequence, code"
    _markdown_fields = ("description",)

    code = fields.Char(required=True, index=True, help="Stable id, e.g. P-3D, MP-11.")
    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    kind = fields.Selection([("project", "Project"), ("mini_project", "Mini-project")], required=True, default="project")
    state = fields.Selection(
        [("candidate", "Candidate"), ("pilot", "Pilot"), ("active", "Active"), ("parked", "Parked"), ("done", "Done")],
        required=True, default="candidate", tracking=True,
    )
    season = fields.Char()
    description = fields.Text(help="Markdown.")
    description_html = markdown_html_field("description")
    carries = fields.Text(string="What it carries", help="The notions this project carries 'by the side'.")
    anchors = fields.Char(help="Interest anchors (free text / emoji).")
    student_vote = fields.Selection([("none", "No answer"), ("up", "Yes"), ("down", "No")], default="none", tracking=True)
    student_reason = fields.Char(help="The student's own words, verbatim.")
    student_id = fields.Many2one("homeschool.student")
    item_ids = fields.Many2many("homeschool.item", "homeschool_item_project_rel", "project_id", "item_id", string="Items (own)")
    block_ids = fields.One2many("homeschool.block", "project_id", string="Blocks")
    trace_ids = fields.One2many("homeschool.trace", "project_id", string="Traces")
    all_item_ids = fields.Many2many(
        "homeschool.item", compute="_compute_all_item_ids", string="Items (with blocks and traces)",
    )
    active = fields.Boolean(default=True)

    _code_unique = models.Constraint("unique(code)", "Project codes must be unique.")

    @api.depends("item_ids", "block_ids.item_ids", "trace_ids.item_ids")
    def _compute_all_item_ids(self):
        for rec in self:
            rec.all_item_ids = rec.item_ids | rec.block_ids.item_ids | rec.trace_ids.item_ids

    @api.model
    def _by_code(self, code):
        return self.with_context(active_test=False).search([("code", "=", code)], limit=1)
