# -*- coding: utf-8 -*-
import string

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .material import DIFFUSION
from .markdown_mixin import markdown_html_field


class Trace(models.Model):
    _name = "homeschool.trace"
    _description = "Learning trace (portfolio artifact)"
    _inherit = ["mail.thread", "homeschool.markdown.mixin", "homeschool.company.mixin"]
    _order = "date desc, code desc"
    _markdown_fields = ("note",)

    code = fields.Char(required=True, index=True, copy=False, default=lambda self: self.env._("New"))
    name = fields.Char(required=True, string="Title")
    date = fields.Date(required=True, default=fields.Date.context_today)
    student_id = fields.Many2one("homeschool.student", required=True, ondelete="cascade", index=True, check_company=True)
    subject_ids = fields.Many2many("homeschool.subject", "homeschool_trace_subject_rel", "trace_id", "subject_id", string="Subjects")
    item_ids = fields.Many2many("homeschool.item", "homeschool_trace_item_rel", "trace_id", "item_id", string="Curriculum items")
    attachment_ids = fields.Many2many("ir.attachment", "homeschool_trace_attachment_rel", "trace_id", "attachment_id", string="Files")
    artifact_path = fields.Char(help="Path of the artifact in the family repository.")
    item_codes = fields.Char(help="Item codes in the order of the family CSV (kept for byte-identical exports).")
    subject_codes = fields.Char(help="Subject codes in the order of the family CSV (kept for byte-identical exports).")
    diffusion = fields.Selection(DIFFUSION, required=True, default="internal", tracking=True)
    note = fields.Text(help="Markdown. The parent's note on the trace.")
    note_html = markdown_html_field("note")
    student_comment = fields.Text(help="The student's own words about this work — portfolio content, never journal.")
    block_id = fields.Many2one("homeschool.block", ondelete="set null", check_company=True)
    project_id = fields.Many2one("homeschool.project", ondelete="set null", check_company=True)
    submitted_by = fields.Selection([("parent", "Parent"), ("student", "Student")], required=True, default="parent")

    _code_unique = models.Constraint("unique(company_id, code)", "Trace codes must be unique within a family.")

    @api.constrains("diffusion", "item_ids")
    def _check_institutional_items(self):
        for rec in self:
            if rec.diffusion == "institutional":
                internal = rec.item_ids.filtered(lambda i: i.kind == "internal")
                if internal:
                    raise ValidationError(self.env._(
                        "An institutional trace cannot reference internal-only items: %s",
                        ", ".join(internal.mapped("code")),
                    ))

    @api.model
    def _next_code(self, date, company=None):
        """Next free 'TR-<date>-<letter>' code within ``company`` (default: the current company)."""
        company = company or self.env.company
        prefix = "TR-%s-" % fields.Date.to_string(date)
        existing = self.with_context(active_test=False).search(
            [("code", "=like", prefix + "%"), ("company_id", "=", company.id)]
        ).mapped("code")
        used = {c[len(prefix):] for c in existing}
        for letter in string.ascii_lowercase:
            if letter not in used:
                return prefix + letter
        raise ValidationError(self.env._("Too many traces on %s.", date))

    @api.model
    def _defaults_from_block(self, block):
        return {
            "date": block.day_id.date,
            "student_id": block.student_id.id,
            "company_id": block.company_id.id,
            "subject_ids": [fields.Command.set(block.subject_id.ids)],
            "item_ids": [fields.Command.set(block.item_ids.ids)],
            "block_id": block.id,
            "project_id": block.project_id.id,
        }

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        block_id = self.env.context.get("default_block_id")
        if block_id:
            block = self.env["homeschool.block"].browse(block_id)
            for key, value in self._defaults_from_block(block).items():
                if key in fields_list and not self.env.context.get("default_" + key):
                    vals[key] = value
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            block_id = vals.get("block_id") or self.env.context.get("default_block_id")
            if block_id:
                block = self.env["homeschool.block"].browse(block_id)
                for key, value in self._defaults_from_block(block).items():
                    vals.setdefault(key, value)
            if not vals.get("code") or vals["code"] == self.env._("New"):
                if vals.get("company_id"):
                    company = self.env["res.company"].browse(vals["company_id"])
                elif vals.get("student_id"):
                    company = self.env["homeschool.student"].browse(vals["student_id"]).company_id
                else:
                    company = self.env.company
                vals["code"] = self._next_code(fields.Date.to_date(vals.get("date") or fields.Date.context_today(self)), company)
        return super().create(vals_list)
