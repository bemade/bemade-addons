# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
from odoo import api, fields, models

from .zeffy_record_mixin import cents, from_timestamp


class ZeffyCampaign(models.Model):
    _name = "zeffy.campaign"
    _inherit = ["zeffy.record.mixin"]
    _description = "Zeffy Campaign"
    _order = "name"

    _unique_zeffy_id = models.Constraint(
        "unique(company_id, zeffy_id)",
        "This Zeffy campaign is already synchronized for this company.",
    )

    name = fields.Char(string="Title", readonly=True)
    campaign_type = fields.Selection(
        [("donation_form", "Donation form"), ("ticketing", "Ticketing")],
        string="Type",
        readonly=True,
    )
    category = fields.Char(readonly=True)
    status = fields.Char(readonly=True)
    url = fields.Char(string="Public page", readonly=True)
    currency_id = fields.Many2one("res.currency", readonly=True)
    goal_amount = fields.Monetary(string="Goal", readonly=True)
    amount_raised = fields.Monetary(string="Raised", readonly=True)
    is_archived = fields.Boolean(string="Archived in Zeffy", readonly=True)
    deleted_at = fields.Datetime(string="Deleted in Zeffy on", readonly=True)
    utm_campaign_id = fields.Many2one(
        "utm.campaign",
        string="UTM Campaign",
        ondelete="set null",
        help="Odoo campaign this Zeffy campaign is reported under.",
    )
    payment_ids = fields.One2many("zeffy.payment", "campaign_id", string="Payments")

    @api.model
    def _zeffy_prepare_values(self, data, company, record, cache):
        vals = {
            "name": data.get("title"),
            "campaign_type": self._zeffy_selection("campaign_type", data.get("type")),
            "category": data.get("category"),
            "status": data.get("status"),
            "url": data.get("url"),
            "currency_id": self._zeffy_currency(data.get("currency"), company, cache).id,
            "goal_amount": cents(data.get("goal_amount") or data.get("target")),
            "amount_raised": cents(data.get("volume")),
            "is_archived": bool(data.get("is_archived")),
            "deleted_at": from_timestamp(data.get("deleted_at")),
        }
        if not record.utm_campaign_id and vals["name"]:
            vals["utm_campaign_id"] = self._zeffy_utm_campaign(vals["name"]).id
        return vals

    @api.model
    def _zeffy_utm_campaign(self, name):
        Utm = self.env["utm.campaign"]
        return Utm.search([("name", "=", name)], limit=1) or Utm.create({"name": name})

    @api.model
    def _zeffy_sync(self, client, company, cache):
        changed = 0
        for data in client.iter_list("campaigns"):
            _record, is_changed = self._zeffy_upsert(data, company, cache)
            changed += is_changed
        return changed

    @api.model
    def _zeffy_get_or_stub(self, zeffy_id, title, company, cache):
        """The campaign of a payment; a stub (overwritten by the next campaign
        synchronization) when Zeffy did not list it."""
        if not zeffy_id:
            return self.browse()
        existing = cache[self._name]
        if zeffy_id not in existing:
            existing[zeffy_id] = self.create(
                {
                    "zeffy_id": zeffy_id,
                    "company_id": company.id,
                    "name": title,
                    "utm_campaign_id": self._zeffy_utm_campaign(title).id if title else False,
                }
            )
        return existing[zeffy_id]
