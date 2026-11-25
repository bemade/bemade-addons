# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
import re

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.fields import Domain
from odoo.tools import str2bool

from odoo.addons.phone_validation.models.mail_thread_phone import PHONE_REGEX_PATTERN

from ..tools import digits, format_number, same_digits, sanitize, split_extension


STORE_INTERNATIONAL_PARAM = "partner_phone_list.store_international"


class ResPartner(models.Model):
    _inherit = "res.partner"

    phone_ids = fields.One2many(
        "res.partner.phone", "partner_id", string="Phone Numbers", copy=True
    )
    phone = fields.Char(
        compute="_compute_phone",
        inverse="_inverse_phone",
        compute_sudo=True,
        store=True,
        readonly=False,
        help="The top number of the contact's phone numbers.",
    )
    mobile = fields.Char(
        compute="_compute_mobile",
        inverse="_inverse_mobile",
        compute_sudo=True,
        store=True,
        readonly=False,
        help="The first Mobile number of the contact's phone numbers.",
    )
    phone_sms_available = fields.Boolean(
        string="SMS Available",
        compute="_compute_phone_sms_available",
        help="Technical: whether text messages can be sent (SMS installed and usable).",
    )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _phone_list_sorted(self):
        self.ensure_one()
        return self.phone_ids.sorted(lambda line: (line.sequence, line._origin.id or 0))

    def _phone_list_country(self):
        country = self.country_id if len(self) == 1 else self.env["res.country"]
        return country or self.env.company.country_id

    def _phone_list_format(self, number):
        """How a number is stored: international format with this contact's
        country (or the company's), the value as typed when it does not
        parse (see ``tools.format_number``)."""
        country = self._phone_list_country()
        return format_number(number, country.code, country.phone_code)

    @api.model
    def _phone_list_store_international(self):
        """Whether numbers written by code are stored in the international
        format (setting « Store phone numbers in international format »)."""
        return str2bool(
            self.env["ir.config_parameter"].sudo().get_param(STORE_INTERNATIONAL_PARAM, "False"),
            default=False,
        )

    def _phone_list_store(self, number):
        """How a written number is stored: in the international format
        (``_phone_list_format``) when the setting is on, as written (trimmed)
        otherwise, like the standard Phone field. Forms format on input
        either way (onchange)."""
        if self._phone_list_store_international():
            return self._phone_list_format(number)
        return number.strip() if isinstance(number, str) else number

    def _phone_list_sanitize(self, number):
        """E.164 form of ``number`` with this contact's country (or the
        company's), False when it does not parse."""
        if not number:
            return False
        country = self._phone_list_country()
        return sanitize(number, country.code, country.phone_code)

    def _phone_list_key(self, number, extension=False):
        self.ensure_one()
        return (self._phone_list_sanitize(number) or digits(number), (extension or "").strip())

    def _phone_list_resequence(self, ordered_lines):
        for index, line in enumerate(ordered_lines):
            sequence = (index + 1) * 10
            if line.sequence != sequence:
                line.sequence = sequence

    def _phone_list_set(self, value, mode):
        """Apply a write of ``phone`` (mode ``top``) or ``mobile`` (mode
        ``mobile``) to the number list. See the module description."""
        self.ensure_one()
        lines = self._phone_list_sorted()
        if not value:
            if mode == "top":
                target = lines[:1]
            else:
                target = lines.filtered(lambda line: line.type == "mobile")[:1]
            target.unlink()
            return
        number, extension = split_extension(value)
        number = self._phone_list_store(number)
        key = self._phone_list_key(number, extension)
        match = lines.filtered(lambda line: line._phone_matches(key, number))[:1]
        was_top = bool(match) and match == lines[:1]
        if match:
            vals = {}
            if match.number != number:
                vals["number"] = number
            if mode == "mobile" and match.type != "mobile":
                vals["type"] = "mobile"
            if vals:
                match.write(vals)
        else:
            match = self.env["res.partner.phone"].create(
                {
                    "partner_id": self.id,
                    "number": number,
                    "extension": extension,
                    "type": "mobile" if mode == "mobile" else "office",
                    "sequence": 0,
                }
            )
        others = [line for line in lines if line != match]
        if mode == "top" or was_top:
            position = 0
        else:
            first_mobile = next(
                (i for i, line in enumerate(others) if line.type == "mobile"), len(others)
            )
            position = min(first_mobile, 1)
        others.insert(position, match)
        self._phone_list_resequence(others)

    @api.model
    def _phone_list_display(self, value):
        """Canonical display of a written phone value (extension parsed)."""
        number, extension = split_extension(value)
        number = self._phone_list_store(number)
        return "%s ext. %s" % (number, extension) if extension else number

    @api.model
    def _phone_list_sms_available(self):
        """Whether text messages can be sent: the SMS module is installed and
        the company has an SMS provider other than Odoo IAP (e.g. Twilio) or
        an IAP account for the SMS service."""
        if "sms.composer" not in self.env:
            return False
        company = self.env.company
        provider = company._fields.get("sms_provider") and company.sms_provider
        if provider and provider != "iap":
            return True
        if "iap.account" not in self.env:
            return False
        return bool(
            self.env["iap.account"]
            .sudo()
            .search_count(
                [
                    ("service_id.technical_name", "=", "sms"),
                    ("account_token", "!=", False),
                    ("state", "!=", "banned"),
                    "|",
                    ("company_ids", "=", False),
                    ("company_ids", "in", company.ids),
                ],
                limit=1,
            )
        )

    @api.model
    def _phone_list_resync(self, records, fname, partner_fname="partner_id"):
        """After ``records`` wrote ``fname`` (a phone field computed from their
        contact's Phone, whose inverse writes it to the contact), recompute it
        on the records whose value is the contact's Phone in another format,
        so they show the stored (formatted) number. Records holding another
        number (not pushed to the contact) are left alone."""
        to_resync = records.browse()
        for record in records:
            partner = record[partner_fname].sudo()
            value = record[fname]
            if not partner or not value or value == partner.phone or not partner.phone:
                continue
            number, extension = split_extension(value)
            key = partner._phone_list_key(partner._phone_list_format(number), extension)
            top = partner._phone_list_sorted()[:1]
            if top and top._phone_matches(key, number):
                to_resync |= record
        if to_resync:
            self.env.add_to_compute(records._fields[fname], to_resync)
        return to_resync

    def _compute_phone_sms_available(self):
        self.phone_sms_available = self._phone_list_sms_available()

    # ------------------------------------------------------------------
    # Computes / inverses
    # ------------------------------------------------------------------

    @api.depends("phone_ids", "phone_ids.sequence", "phone_ids.number", "phone_ids.extension")
    def _compute_phone(self):
        for partner in self:
            top = partner._phone_list_sorted()[:1]
            if top:
                partner.phone = top._phone_display()
            elif partner._origin.id:
                partner.phone = False
            else:
                # new record (form): keep a value typed in a Phone field
                partner.phone = partner.phone

    @api.depends("phone_ids", "phone_ids.sequence", "phone_ids.number", "phone_ids.type")
    def _compute_mobile(self):
        for partner in self:
            mobile = partner._phone_list_sorted().filtered(lambda line: line.type == "mobile")[:1]
            if mobile:
                partner.mobile = mobile.number
            elif partner._origin.id:
                partner.mobile = False
            else:
                partner.mobile = partner.mobile

    # The inverses run once the write of the contact itself passed the access
    # checks: whoever may change a contact's Phone / Mobile (a portal user on
    # their own address, a website form...) changes its number list, without
    # needing rights on the number model.

    def _inverse_phone(self):
        for partner in self:
            partner.sudo()._phone_list_set(partner.phone, "top")

    def _inverse_mobile(self):
        for partner in self:
            partner.sudo()._phone_list_set(partner.mobile, "mobile")

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    @api.model
    def _phone_list_prepare_vals(self, vals):
        if "phone_ids" in vals:
            # the list wins over Phone / Mobile sent along with it
            vals = {k: v for k, v in vals.items() if k not in ("phone", "mobile")}
        # Some callers (imports, other modules' tests) send numbers as int.
        for fname in ("phone", "mobile"):
            if vals.get(fname) and not isinstance(vals[fname], str):
                vals = dict(vals, **{fname: str(vals[fname])})
        if vals.get("phone"):
            vals = dict(vals, phone=self._phone_list_display(vals["phone"]))
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._phone_list_prepare_vals(vals) for vals in vals_list]
        partners = super().create(vals_list)
        # Phone / Mobile were protected while their inverse filled the list:
        # recompute them so they show the stored (formatted) numbers.
        for fname in ("phone", "mobile"):
            written = partners.browse(
                [p.id for p, vals in zip(partners, vals_list, strict=True) if vals.get(fname)]
            )
            if written:
                self.env.add_to_compute(self._fields[fname], written)
        return partners

    def write(self, vals):
        vals = self._phone_list_prepare_vals(vals)
        written = [fname for fname in ("phone", "mobile") if fname in vals]
        log = "phone_ids" in vals and not self.env.context.get("tracking_disable")
        before = {}
        if log:
            before = {partner.id: (partner.phone, partner._phone_list_summary()) for partner in self}
        res = super().write(vals)
        if written:
            # Phone / Mobile were protected while their inverse changed the
            # list: recompute them now so they reflect the list (e.g. the next
            # number after clearing Phone).
            for fname in written:
                self.env.add_to_compute(self._fields[fname], self)
        if log:
            for partner in self:
                old_phone, old_summary = before[partner.id]
                new_summary = partner._phone_list_summary()
                # a change of the top number is already tracked through Phone
                if new_summary != old_summary and partner.phone == old_phone:
                    partner._message_log(
                        body=Markup("<p>%s</p><ul>%s</ul>")
                        % (
                            _("Phone numbers updated:"),
                            Markup("").join(Markup("<li>%s</li>") % item for item in new_summary)
                            or Markup("<li>-</li>"),
                        )
                    )
        return res

    def _phone_list_summary(self):
        self.ensure_one()
        labels = dict(self.env["res.partner.phone"]._fields["type"]._description_selection(self.env))
        return [
            "%s: %s%s"
            % (labels.get(line.type, line.type), line._phone_display(), " (%s)" % line.label if line.label else "")
            for line in self._phone_list_sorted()
        ]

    # ------------------------------------------------------------------
    # Search: any number of the list
    # ------------------------------------------------------------------

    def _search_phone_mobile_search(self, operator, value):
        domain = super()._search_phone_mobile_search(operator, value)
        if operator not in ("=", "like", "ilike", "=like", "=ilike") or not isinstance(value, str):
            return domain
        value = value.strip()
        term = re.sub(PHONE_REGEX_PATTERN, "", value)
        if term.startswith("+"):
            term = term[1:]
        elif term.startswith("00"):
            term = term[2:]
        if len(term) < 3:
            return domain
        sanitized = self._phone_list_sanitize(value) if operator == "=" else False
        self.env["res.partner.phone"].flush_model(["partner_id", "number", "number_sanitized"])
        if operator == "=":
            self.env.cr.execute(
                f"""SELECT partner_id FROM res_partner_phone
                     WHERE REGEXP_REPLACE(number, %s, '', 'g') = %s
                        OR number_sanitized = %s
                        OR number_sanitized = %s""",
                (PHONE_REGEX_PATTERN, value, sanitized or "", "+" + term),
            )
        else:
            self.env.cr.execute(
                f"""SELECT partner_id FROM res_partner_phone
                     WHERE REGEXP_REPLACE(number, %s, '', 'g') LIKE %s
                        OR number_sanitized LIKE %s""",
                (PHONE_REGEX_PATTERN, "%" + term + "%", "%" + term + "%"),
            )
        partner_ids = [row[0] for row in self.env.cr.fetchall()]
        if not partner_ids:
            return domain
        return Domain.OR([domain, Domain("id", "in", partner_ids)])

    # ------------------------------------------------------------------
    # Merge support (base merge wizard, and any SQL-level merge tool)
    # ------------------------------------------------------------------

    def _phone_list_prepare_merge(self, src_partners):
        """Before the lines of ``src_partners`` are moved onto ``self`` by SQL:
        delete the source lines that duplicate a number already kept (the
        unique index would make the move fail) and number the others after
        the kept contact's own lines."""
        self.ensure_one()
        dst = self.sudo()
        kept = dst._phone_list_sorted()
        seen = [(dst._phone_list_key(line.number, line.extension), line.number) for line in kept]
        sequence = max(kept.mapped("sequence"), default=0)
        duplicates = self.env["res.partner.phone"].sudo()
        for partner in src_partners.sudo():
            for line in partner._phone_list_sorted():
                key = dst._phone_list_key(line.number, line.extension)
                if any(k == key and same_digits(n, line.number) for k, n in seen):
                    duplicates |= line
                    continue
                seen.append((key, line.number))
                sequence += 10
                line.sequence = sequence
        duplicates.unlink()
        self.env.flush_all()

    def _phone_list_after_merge(self, *others):
        """After an SQL move of lines onto ``self``: recompute what the SQL
        bypassed (sanitized numbers with the kept contact's country, Phone,
        Mobile), also on ``others`` (source contacts that are kept)."""
        self.env.invalidate_all()
        partners = self.browse(self.ids).union(*others)
        Line = self.env["res.partner.phone"].sudo()
        lines = Line.search([("partner_id", "in", partners.ids)])
        self.env.add_to_compute(Line._fields["number_sanitized"], lines)
        self.env.add_to_compute(self._fields["phone"], partners)
        self.env.add_to_compute(self._fields["mobile"], partners)
        self.env.flush_all()
