# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
import functools

from odoo import api, fields, models
from odoo.exceptions import AccessError

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
            partner = line.partner_id
            formatted = False
            if partner:
                formatted = partner._phone_format(number=number, force_format="INTERNATIONAL")
            line.number = formatted or number

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
    def _phone_normalize_vals(self, vals):
        if vals.get("number"):
            number, extension = split_extension(vals["number"])
            if extension and not vals.get("extension"):
                vals = dict(vals, number=number, extension=extension)
            else:
                vals = dict(vals, number=vals["number"].strip())
        if isinstance(vals.get("extension"), str):
            vals = dict(vals, extension=vals["extension"].strip() or False)
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        return super().create([self._phone_normalize_vals(vals) for vals in vals_list])

    def write(self, vals):
        return super().write(self._phone_normalize_vals(vals))

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
