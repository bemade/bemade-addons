# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
import datetime
import hashlib
import json
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


def cents(value):
    """Zeffy amounts are integer cents."""
    return (value or 0) / 100.0


def from_timestamp(value):
    """Zeffy timestamps are Unix seconds; Odoo stores naive UTC."""
    if not value:
        return False
    return datetime.datetime.fromtimestamp(value, tz=datetime.UTC).replace(tzinfo=None)


class ZeffyRecordMixin(models.AbstractModel):
    """A record mirrored from a Zeffy API object, keyed on its Zeffy id."""

    _name = "zeffy.record.mixin"
    _description = "Zeffy Record"

    zeffy_id = fields.Char(string="Zeffy ID", required=True, readonly=True, index=True, copy=False)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        readonly=True,
        index=True,
        default=lambda self: self.env.company,
    )
    zeffy_checksum = fields.Char(readonly=True, copy=False)

    @api.model
    def _zeffy_checksum(self, data):
        raw = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    @api.model
    def _zeffy_existing(self, company):
        """Map Zeffy id -> record for one company, archived included."""
        records = self.with_context(active_test=False).search([("company_id", "=", company.id)])
        return {record.zeffy_id: record for record in records}

    @api.model
    def _zeffy_prepare_values(self, data, company, record, cache):
        """Odoo values for one Zeffy API object. ``record`` is the existing
        record, or an empty recordset on creation."""
        raise NotImplementedError

    @api.model
    def _zeffy_upsert(self, data, company, cache):
        """Create or update the record of one Zeffy API object.

        ``cache[self._name]`` maps Zeffy id -> record for ``company``.
        Return ``(record, changed)``; an unchanged payload writes nothing.
        """
        existing = cache[self._name]
        record = existing.get(data["id"], self.browse())
        checksum = self._zeffy_checksum(data)
        if record and record.zeffy_checksum == checksum:
            return record, False
        vals = self._zeffy_prepare_values(data, company, record, cache)
        vals["zeffy_checksum"] = checksum
        if record:
            record.write(vals)
        else:
            vals.update(zeffy_id=data["id"], company_id=company.id)
            record = self.create(vals)
            existing[data["id"]] = record
        return record, True

    @api.model
    def _zeffy_selection(self, field_name, value):
        """``value`` if the selection field knows it, else False (logged), so
        a value Zeffy adds later never breaks a synchronization."""
        if not value:
            return False
        keys = [key for key, _label in self._fields[field_name]._description_selection(self.env)]
        if value in keys:
            return value
        _logger.warning("Unknown Zeffy value %r for %s.%s", value, self._name, field_name)
        return False

    @api.model
    def _zeffy_currency(self, code, company, cache):
        currencies = cache.setdefault("res.currency", {})
        code = (code or "").upper()
        if code not in currencies:
            currency = self.env["res.currency"].with_context(active_test=False).search(
                [("name", "=", code)], limit=1
            )
            currencies[code] = currency or company.currency_id
        return currencies[code]
