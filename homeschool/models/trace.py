# -*- coding: utf-8 -*-
import string

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError

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
    submitted_by = fields.Selection(
        [("parent", "Parent"), ("student", "Student"), ("resource", "Resource")], required=True, default="parent",
        help="Who handed the trace in. A trace submitted from the portal (student, resource) waits for the "
        "parent's validation before it can leave the house.",
    )
    validated = fields.Boolean(
        default=True, tracking=True, copy=False,
        help="Parent-created traces are validated; a trace submitted by the student or a resource user is "
        "not until the parent validates it. A non-validated trace cannot be institutional.",
    )
    validated_by = fields.Many2one("res.users", readonly=True, copy=False)
    validated_at = fields.Datetime(readonly=True, copy=False)

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

    @api.constrains("validated", "diffusion")
    def _check_validated_institutional(self):
        for rec in self:
            if rec.diffusion == "institutional" and not rec.validated:
                raise ValidationError(self.env._(
                    "%s: a trace must be validated before it becomes institutional.", rec.code
                ))

    @api.model
    def _next_code(self, date, company=None):
        """Next free 'TR-<date>-<letter>' code within ``company`` (default: the current company).
        Searched as superuser: a portal submitter only sees a few traces and must not reuse a code."""
        company = company or self.env.company
        prefix = "TR-%s-" % fields.Date.to_string(date)
        existing = self.sudo().with_context(active_test=False).search(
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
            # a portal user has no access to the curriculum: create() links the block's
            # subjects and items itself, as superuser
            skip = {"subject_ids", "item_ids"} if self.env.user.share and not self.env.su else set()
            for key, value in self._defaults_from_block(block).items():
                if key in fields_list and key not in skip and not self.env.context.get("default_" + key):
                    vals[key] = value
        return vals

    def _portal_submitted_by(self, student):
        """How the current (portal) user relates to ``student``: 'student' for his own login,
        'resource' when he is one of the student's resource users, else AccessError."""
        student = student.sudo()
        if student and student.user_id == self.env.user:
            return "student"
        if student and self.env.user in student.resource_user_ids:
            return "resource"
        raise AccessError(self.env._(
            "You can only submit a trace for your own student or for a student you are attached to."
        ))

    def _guard_portal_submission(self, vals):
        """A trace created from the portal is always internal and pending, and says who
        submitted it; the submitter cannot pretend otherwise."""
        student = self.env["homeschool.student"].browse(vals.get("student_id") or [])
        vals["submitted_by"] = self._portal_submitted_by(student)
        vals["diffusion"] = "internal"
        vals["validated"] = False
        vals.pop("validated_by", None)
        vals.pop("validated_at", None)
        vals["company_id"] = student.sudo().company_id.id

    @api.model_create_multi
    def create(self, vals_list):
        portal = self.env.user.share and not self.env.su
        portal_tags = []  # per record: the block's subjects and items, written as superuser below
        for vals in vals_list:
            block_id = vals.get("block_id") or self.env.context.get("default_block_id")
            block_defaults = self._defaults_from_block(self.env["homeschool.block"].browse(block_id)) if block_id else {}
            for key, value in block_defaults.items():
                vals.setdefault(key, value)
            if portal:
                self._guard_portal_submission(vals)
                # a portal user has no access to the curriculum: the trace takes its block's
                # subjects and items (nothing else), linked after creation as superuser
                vals.pop("subject_ids", None)
                vals.pop("item_ids", None)
                portal_tags.append({k: block_defaults[k] for k in ("subject_ids", "item_ids") if k in block_defaults})
            elif "validated" not in vals:
                vals["validated"] = vals.get("submitted_by", "parent") == "parent"
            if not vals.get("code") or vals["code"] == self.env._("New"):
                if vals.get("company_id"):
                    company = self.env["res.company"].browse(vals["company_id"])
                elif vals.get("student_id"):
                    company = self.env["homeschool.student"].browse(vals["student_id"]).company_id
                else:
                    company = self.env.company
                vals["code"] = self._next_code(fields.Date.to_date(vals.get("date") or fields.Date.context_today(self)), company)
        traces = super().create(vals_list)
        for trace, tags in zip(traces, portal_tags):
            if tags:
                trace.sudo().write(tags)
        traces.sudo()._ensure_item_coverage()
        return traces

    def action_validate(self, diffusion=None):
        """The parent validates a submitted trace (and may set its diffusion in the same
        move). Managers only: the button is theirs, and a portal user calling it over RPC
        is refused before anything is written."""
        if not self.env.su and not self.env.user.has_group("homeschool.group_homeschool_manager"):
            raise AccessError(self.env._("Only a homeschool manager can validate a trace."))
        vals = {"validated": True, "validated_by": self.env.user.id, "validated_at": fields.Datetime.now()}
        if diffusion:
            vals["diffusion"] = diffusion
        self.write(vals)
        return True

    def write(self, vals):
        result = super().write(vals)
        if "item_ids" in vals or "company_id" in vals:
            self._ensure_item_coverage()
        return result

    def _ensure_item_coverage(self):
        """A trace evidences its items for its family: make sure the family's coverage rows exist."""
        Coverage = self.env["homeschool.item.coverage"]
        for company, traces in self.grouped("company_id").items():
            Coverage._ensure_rows(traces.item_ids, company)
