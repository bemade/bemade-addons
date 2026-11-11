# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
from odoo import _, api, fields, models
from odoo.tools import escape_psql

from .zeffy_record_mixin import cents, from_timestamp


def _normalize_zip(value):
    return "".join((value or "").split()).upper()


class ZeffyContact(models.Model):
    _name = "zeffy.contact"
    _inherit = ["zeffy.record.mixin"]
    _description = "Zeffy Contact"
    _order = "name"

    _unique_zeffy_id = models.Constraint(
        "unique(company_id, zeffy_id)",
        "This Zeffy contact is already synchronized for this company.",
    )

    name = fields.Char(readonly=True)
    first_name = fields.Char(readonly=True)
    last_name = fields.Char(readonly=True)
    email = fields.Char(readonly=True)
    phone = fields.Char(readonly=True)
    street = fields.Char(readonly=True)
    city = fields.Char(readonly=True)
    zip = fields.Char(string="Postal code", readonly=True)
    state_code = fields.Char(string="Province / state", readonly=True)
    country_code = fields.Char(string="Country", readonly=True)
    donor_type = fields.Char(readonly=True)
    currency_id = fields.Many2one("res.currency", readonly=True)
    total_contribution = fields.Monetary(readonly=True)
    donation_count = fields.Integer(string="Donations", readonly=True)
    first_donation_date = fields.Datetime(readonly=True)
    last_donation_date = fields.Datetime(readonly=True)
    zeffy_updated = fields.Datetime(string="Updated in Zeffy", readonly=True)
    partner_id = fields.Many2one(
        "res.partner",
        string="Contact",
        index=True,
        ondelete="set null",
        help="Odoo contact this Zeffy contact is linked to. Set automatically "
        "on the first synchronization; change it to correct a wrong match.",
    )
    payment_ids = fields.One2many("zeffy.payment", "contact_id", string="Payments")

    @api.model
    def _zeffy_prepare_values(self, data, company, record, cache):
        address = data.get("address") or {}
        vals = {
            "name": self._zeffy_full_name(data) or data.get("email"),
            "first_name": data.get("first_name"),
            "last_name": data.get("last_name"),
            "email": data.get("email"),
            "phone": data.get("phone_number"),
            "street": address.get("line1"),
            "city": address.get("city"),
            "zip": address.get("postal_code"),
            "state_code": address.get("state"),
            "country_code": address.get("country"),
            "donor_type": data.get("donor_type"),
            "currency_id": self._zeffy_currency(data.get("currency"), company, cache).id,
            "total_contribution": cents(data.get("total_contribution")),
            "donation_count": data.get("donation_count") or 0,
            "first_donation_date": from_timestamp(data.get("first_donation_date")),
            "last_donation_date": from_timestamp(data.get("last_donation_date")),
            "zeffy_updated": from_timestamp(data.get("updated")),
        }
        if not record.partner_id:
            vals["partner_id"] = self._zeffy_match_partner(
                company,
                email=data.get("email"),
                first_name=data.get("first_name"),
                last_name=data.get("last_name"),
                phone=data.get("phone_number"),
                address=address,
            ).id
        return vals

    @api.model
    def _zeffy_full_name(self, data):
        return " ".join(filter(None, [data.get("first_name"), data.get("last_name")])).strip()

    @api.model
    def _zeffy_match_partner(
        self, company, email=None, first_name=None, last_name=None, phone=None, address=None, company_name=None
    ):
        """The Odoo contact of a Zeffy donor: same email, else same name and
        postal code, else a new person. An existing contact is never
        modified."""
        Partner = self.env["res.partner"]
        address = address or {}
        scope = ["|", ("company_id", "=", False), ("company_id", "=", company.id)]
        email = (email or "").strip()
        if email:
            partner = Partner.search(scope + [("email", "=ilike", escape_psql(email))], order="id", limit=1)
            if partner:
                return partner
        name = self._zeffy_full_name({"first_name": first_name, "last_name": last_name})
        postal_code = _normalize_zip(address.get("postal_code"))
        if name and postal_code:
            candidates = Partner.search(
                scope + [("name", "=ilike", escape_psql(name)), ("zip", "!=", False)], order="id"
            )
            for partner in candidates:
                if _normalize_zip(partner.zip) == postal_code:
                    return partner
        country = self.env["res.country"]
        if address.get("country"):
            country = country.search([("code", "=", address["country"].upper())], limit=1)
        state = self.env["res.country.state"]
        if address.get("state") and country:
            state = state.search(
                [("code", "=", address["state"].upper()), ("country_id", "=", country.id)], limit=1
            )
        return Partner.create(
            {
                "name": name or email or _("Zeffy donor"),
                "company_type": "person",
                "company_name": company_name or False,
                "email": email or False,
                "phone": phone or False,
                "street": address.get("line1") or False,
                "city": address.get("city") or False,
                "zip": address.get("postal_code") or False,
                "state_id": state.id,
                "country_id": country.id,
            }
        )

    @api.model
    def _zeffy_sync(self, client, company, cache):
        params = {}
        if company.zeffy_contact_watermark:
            params["updated[gte]"] = company.zeffy_contact_watermark
        watermark = company.zeffy_contact_watermark
        changed = 0
        for data in client.iter_list("contacts", params):
            _record, is_changed = self._zeffy_upsert(data, company, cache)
            changed += is_changed
            watermark = max(watermark, data.get("updated") or 0)
        # Only advanced after a complete pass: an interrupted one is re-read.
        company.zeffy_contact_watermark = watermark
        return changed

    @api.model
    def _zeffy_from_buyer(self, zeffy_id, buyer, company, cache):
        """The Zeffy contact of a payment, built from the payment's buyer when
        the contact was not synchronized yet. Left without checksum so the
        next contact synchronization completes it."""
        existing = cache[self._name]
        if zeffy_id not in existing:
            data = {
                "first_name": buyer.get("first_name"),
                "last_name": buyer.get("last_name"),
                "email": buyer.get("email"),
            }
            address = buyer.get("address") or {}
            existing[zeffy_id] = self.create(
                {
                    "zeffy_id": zeffy_id,
                    "company_id": company.id,
                    "name": self._zeffy_full_name(data) or data["email"],
                    "first_name": data["first_name"],
                    "last_name": data["last_name"],
                    "email": data["email"],
                    "street": address.get("line1"),
                    "city": address.get("city"),
                    "zip": address.get("postal_code"),
                    "state_code": address.get("state"),
                    "country_code": address.get("country"),
                    "partner_id": self._zeffy_match_partner(
                        company,
                        email=data["email"],
                        first_name=data["first_name"],
                        last_name=data["last_name"],
                        address=address,
                        company_name=buyer.get("company_name") if buyer.get("is_corporate") else None,
                    ).id,
                }
            )
        return existing[zeffy_id]
