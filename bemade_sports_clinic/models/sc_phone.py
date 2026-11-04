"""Task 1645 — one phone rule for every phone field of the clinic.

``sc_normalize_phone`` formats a number the way the backend onchange always
did (INTERNATIONAL: ``+1 514-555-0123``) and refuses one that does not parse
(« Invalid phone number. »). ``sc.phone.mixin`` applies it in create / write
of the models that carry a phone (players, emergency contacts, team staff):
the app, the portal forms and the backend all go through it, not only the
backend onchange.

* Only the phone fields actually written are checked, and a value equal to
  the stored one is left as is (an unrelated save never trips on an old
  invalid number).
* Lenient — format a valid number, keep an invalid one as is, never refuse —
  in imports (``import_file``), module install / upgrade (``install_mode``,
  migrations), an explicit ``sc_phone_lenient`` context, and superuser
  writes outside an HTTP request (scripts, crons, roster imports).
* Extensions: « x123 » / « ext. 123 » / « poste 123 » are kept
  (``+1 514-555-0123 ext. 123``).
* Without the optional ``phonenumbers`` library nothing can be checked: the
  value is kept as typed.
"""
import re

from odoo import api, models
from odoo.exceptions import UserError, ValidationError
from odoo.http import request

from odoo.addons.phone_validation.tools import phone_validation

_EXTENSION_RE = re.compile(r"\s*(?:poste|post\.?|ext\.?|extension)\s*(\d+)\s*$", re.IGNORECASE)


def _prepare(value):
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return _EXTENSION_RE.sub(r" x\1", text)


def sc_normalize_phone(env, value, country=None, strict=True):
    """``value`` formatted INTERNATIONAL; False when empty. An invalid number
    raises « Invalid phone number. » when ``strict``, else comes back as
    typed (stripped)."""
    text = _prepare(value)
    if not text:
        return False
    country = country or env.company.country_id or env.ref("base.ca", raise_if_not_found=False)
    try:
        return phone_validation.phone_format(
            text,
            country.code if country else None,
            country.phone_code if country else None,
            force_format="INTERNATIONAL",
            raise_exception=True,
        )
    except UserError:
        if strict:
            raise ValidationError(env._("Invalid phone number.")) from None
        return str(value).strip()


def sc_phone_is_valid(env, value, country=None):
    """True for an empty or a parseable number (formatted or not)."""
    try:
        sc_normalize_phone(env, value, country=country, strict=True)
    except ValidationError:
        return False
    return True


class ScPhoneMixin(models.AbstractModel):
    _name = "sc.phone.mixin"
    _description = "Sports clinic: phone normalization"

    # The phone fields of the model, normalized in create / write.
    _sc_phone_fields = ()

    def _sc_phone_country(self, vals=None):
        """The country a national number is read in (the record's, else the
        company's)."""
        return self.env.company.country_id

    @api.model
    def _sc_phone_lenient(self):
        ctx = self.env.context
        if ctx.get("import_file") or ctx.get("sc_phone_lenient") or ctx.get("install_mode"):
            return True
        if self.pool._init or not self.pool.ready:
            return True  # module install / upgrade, migrations
        return bool(self.env.su and not request)

    def _sc_phone_vals(self, vals, record=None):
        strict = not self._sc_phone_lenient()
        country = (record or self)._sc_phone_country(vals)
        for name in self._sc_phone_fields:
            if name not in vals:
                continue
            value = vals[name]
            if record is not None and (value or False) == (record[name] or False):
                continue  # unchanged: never re-validate a stored value
            vals[name] = sc_normalize_phone(self.env, value, country=country, strict=strict)
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if any(name in vals for name in self._sc_phone_fields):
                self._sc_phone_vals(vals)
        return super().create(vals_list)

    def write(self, vals):
        if not any(name in vals for name in self._sc_phone_fields):
            return super().write(vals)
        if len(self) <= 1:
            return super().write(self._sc_phone_vals(dict(vals), record=self[:1] or None))
        for record in self:
            super(ScPhoneMixin, record).write(record._sc_phone_vals(dict(vals), record=record))
        return True
