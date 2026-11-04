# -*- coding: utf-8 -*-
from odoo import api, models


class AttachmentMixin(models.AbstractModel):
    """A record that carries files through ``ir.attachment`` relations.

    A file uploaded in the backend before its record is saved (the many2many binary
    widget, the many2one binary widget) is created with ``res_id = 0``: nobody but its
    uploader and the administrators may read it afterwards, so it stays invisible on the
    portal. This mixin stamps every attachment linked through ``_attachment_fields`` with
    the record's model and id as soon as the link is made, on create and on write. The
    stamp is written as superuser: the write on the record itself was already allowed,
    and the attachment is only being told which record it belongs to.
    """
    _name = "homeschool.attachment.mixin"
    _description = "Record carrying files"

    # the fields (many2many or many2one to ir.attachment) whose files belong to the record
    _attachment_fields = ("attachment_ids",)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        touched = records.browse([
            rec.id for rec, vals in zip(records, vals_list)
            if any(name in vals for name in self._attachment_fields)
        ])
        touched._stamp_attachments()
        return records

    def write(self, vals):
        result = super().write(vals)
        if any(name in vals for name in self._attachment_fields):
            self._stamp_attachments()
        return result

    def _stamp_attachments(self):
        """Give every linked attachment still without a record (``res_id`` 0 or no
        ``res_model``) this record as its owner."""
        for rec in self.sudo():
            attachments = rec.env["ir.attachment"]
            for name in self._attachment_fields:
                attachments |= rec[name]
            orphans = attachments.filtered(lambda a: not a.res_id or not a.res_model)
            if orphans:
                orphans.write({"res_model": rec._name, "res_id": rec.id})
