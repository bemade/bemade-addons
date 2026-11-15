# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
import functools

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from ..tools import digits, same_digits, split_extension

PHONE_TYPES = [
    ("mobile", "Mobile"),
    ("office", "Office"),
    ("direct", "Direct line"),
    ("tollfree", "Toll-free"),
    ("home", "Home"),
    ("fax", "Fax"),
    ("other", "Other"),
]


class ResPartnerPhone(models.Model):
    _name = "res.partner.phone"
    _description = "Contact Phone Number"
    _order = "partner_id, sequence, id"
    _rec_name = "number"

    partner_id = fields.Many2one(
        "res.partner", string="Contact", required=True, ondelete="cascade", index=True
    )
    sequence = fields.Integer(default=10, help="The top number is the contact's Phone.")
    type = fields.Selection(PHONE_TYPES, required=True, default="office")
    number = fields.Char(required=True)
    extension = fields.Char()
    label = fields.Char(help="Free note, e.g. after hours, reception.")
    number_sanitized = fields.Char(
        string="Sanitized Number",
        compute="_compute_number_sanitized",
        store=True,
        index="btree_not_null",
        help="The number in E.164 form, used to match and search numbers.",
    )
    sms_available = fields.Boolean(
        string="SMS Available",
        compute="_compute_sms_available",
        help="Technical: whether text messages can be sent (SMS installed and usable).",
    )

    # Same number twice on a contact. The digits are part of the key because
    # the E.164 parser ignores trailing text: "514-555-0101, 123" and
    # "514-555-0101, 456" (legacy data) share a sanitized form yet differ.
    _number_unique = models.UniqueIndex(
        "(partner_id, number_sanitized, COALESCE(extension, ''),"
        " REGEXP_REPLACE(number, '[^0-9]', '', 'g')) WHERE number_sanitized IS NOT NULL",
        "This number is already in the contact's phone numbers.",
    )

    # ------------------------------------------------------------------
    # Computes / onchange
    # ------------------------------------------------------------------

    @api.depends("number", "partner_id.country_id")
    def _compute_number_sanitized(self):
        for line in self:
            line.number_sanitized = line.partner_id._phone_list_sanitize(line.number)

    def _compute_sms_available(self):
        self.sms_available = self.env["res.partner"]._phone_list_sms_available()

    @api.depends("number", "extension", "type")
    def _compute_display_name(self):
        labels = dict(self._fields["type"]._description_selection(self.env))
        for line in self:
            line.display_name = "%s (%s)" % (line._phone_display(), labels.get(line.type, ""))

    @api.onchange("number")
    def _onchange_number_format(self):
        """Format a typed number like the standard Phone field does, and move
        a typed extension to the extension column."""
        for line in self:
            if not line.number:
                continue
            number, extension = split_extension(line.number)
            if extension and not line.extension:
                line.extension = extension
            elif extension:
                number = line.number
            line.number = line.partner_id._phone_list_format(number)

    def _phone_display(self):
        self.ensure_one()
        # not translated: the result is stored in the contact's Phone
        if self.extension:
            return "%s ext. %s" % (self.number or "", self.extension)
        return self.number or ""

    def _phone_key(self):
        """Matching key, see ``res.partner._phone_list_key``."""
        self.ensure_one()
        return (self.number_sanitized or digits(self.number), (self.extension or "").strip())

    def _phone_matches(self, key, number):
        """Whether this line holds ``number`` (whose key is ``key``): same
        sanitized number and extension, and the same digits."""
        self.ensure_one()
        return self._phone_key() == key and same_digits(self.number, number)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    @api.model
    def default_get(self, fields):
        # ``default_type`` in the context usually targets res.partner.type
        # (e.g. the child-contact popup): ignore values that are not ours.
        if self.env.context.get("default_type") not in (None, *dict(PHONE_TYPES)):
            self = self.with_context(default_type=None)
        return super().default_get(fields)

    @api.model
    def _phone_normalize_vals(self, vals, partner):
        """Move a typed extension to its column and store the number as
        ``res.partner._phone_list_store`` says (international format when the
        setting is on, as written otherwise)."""
        if vals.get("number"):
            number, extension = split_extension(vals["number"])
            if extension and not vals.get("extension"):
                vals = dict(vals, extension=extension)
            else:
                number = vals["number"]
            vals = dict(vals, number=partner._phone_list_store(number))
        if isinstance(vals.get("extension"), str):
            vals = dict(vals, extension=vals["extension"].strip() or False)
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        Partner = self.env["res.partner"]
        return super().create(
            [
                self._phone_normalize_vals(vals, Partner.browse(vals.get("partner_id")))
                for vals in vals_list
            ]
        )

    def write(self, vals):
        if not vals.get("number"):
            return super().write(self._phone_normalize_vals(vals, self.env["res.partner"]))
        if "partner_id" in vals:
            partner = self.env["res.partner"].browse(vals["partner_id"])
            return super().write(self._phone_normalize_vals(vals, partner))
        # the format depends on each contact's country
        for partner, lines in self.grouped("partner_id").items():
            super(ResPartnerPhone, lines).write(self._phone_normalize_vals(vals, partner))
        return True

    # ------------------------------------------------------------------
    # SMS
    # ------------------------------------------------------------------

    def action_send_sms(self):
        """Open the SMS composer on the contact for this Mobile number."""
        self.ensure_one()
        if self.type != "mobile":
            raise UserError(self.env._("Text messages can only be sent to a Mobile number."))
        if not self.env["res.partner"]._phone_list_sms_available():
            raise UserError(self.env._("Text messages cannot be sent from this database."))
        partner = self.partner_id
        context = {
            "default_res_model": "res.partner",
            "default_res_id": partner.id,
            "default_composition_mode": "comment",
            "default_number_field_name": "mobile",
            "dialog_size": "medium",
        }
        first_mobile = partner._phone_list_sorted().filtered(lambda line: line.type == "mobile")[:1]
        if first_mobile != self:
            # another Mobile number: the composer records it as the
            # contact's Mobile when sending (standard SMS behaviour)
            context["default_recipient_single_number_itf"] = self.number
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Send SMS"),
            "res_model": "sms.composer",
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "new",
            "context": context,
        }

    # ------------------------------------------------------------------
    # Access: a number follows its contact (read = read the contact,
    # create / write / unlink = write the contact).
    # ------------------------------------------------------------------

    def _check_access(self, operation):
        result = super()._check_access(operation)
        if result or not self or not any(self._ids):
            return result
        partner_operation = "read" if operation == "read" else "write"
        lines = self.sudo().filtered("partner_id")
        partners = lines.partner_id
        allowed = partners.with_env(self.env)._filtered_access(partner_operation)
        forbidden = lines.filtered(lambda line: line.partner_id not in allowed).with_env(self.env)
        if not forbidden:
            return None

        def make_error():
            return AccessError(
                self.env._(
                    "You are not allowed to change the phone numbers of %(contacts)s.",
                    contacts=", ".join(forbidden.sudo().partner_id.mapped("display_name")),
                )
                if partner_operation == "write"
                else self.env._("You are not allowed to see these phone numbers.")
            )

        return forbidden, functools.partial(make_error)
