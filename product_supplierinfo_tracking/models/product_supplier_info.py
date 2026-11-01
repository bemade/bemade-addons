# -*- coding: utf-8 -*-

from markupsafe import Markup

from odoo import _, fields, models
from odoo.tools.misc import (
    NON_BREAKING_SPACE as NBSP,
    format_date,
    format_datetime,
    formatLang,
    get_lang,
)


class ProductSupplierInfo(models.Model):
    _name = "product.supplierinfo"
    _inherit = ["product.supplierinfo", "mail.thread", "mail.activity.mixin"]

    # Commented out because breaking basic Odoo tests. See if this is really needed.

    # _sql_constraints = [("supplierinfo_product_tmpl_id_no_null",
    #                      "CHECK((product_tmpl_id IS NOT NULL))",
    #                      "Supplier pricelist need product template"),
    #                     ]

    # We add tracking to the fields that are displayed in the chatter
    partner_id = fields.Many2one(tracking=True, domain=[("is_company", "=", True)])

    partner_id = fields.Many2one(tracking=True)
    product_name = fields.Char(tracking=True)
    product_code = fields.Char(tracking=True)
    product_uom_id = fields.Many2one(tracking=True)
    min_qty = fields.Float(tracking=True)
    currency_id = fields.Many2one(tracking=True)
    date_start = fields.Date(tracking=True)
    date_end = fields.Date(tracking=True)
    product_id = fields.Many2one(tracking=True)
    product_tmpl_id = fields.Many2one(tracking=True)
    delay = fields.Integer(tracking=True)
    price = fields.Float(tracking=True)
    discount = fields.Float(tracking=True)
    delay = fields.Integer(tracking=True)

    # Float fields of the line shown as money in the line's currency.
    _chatter_money_fields = ("price", "price_discounted")

    def _chatter_format_money(self, amount):
        """Amount in the line's currency, with at least two decimals and never
        fewer than the value carries (vendor prices are not rounded: 5.945
        stays 5.945, 12 becomes 12.00)."""
        decimals = f"{amount:.10f}".rstrip("0").partition(".")[2]
        digits = max(2, len(decimals))
        currency = self.currency_id or self.env.company.currency_id
        value = formatLang(self.env, amount, digits=digits)
        if not currency.symbol:
            return value
        if currency.position == "after":
            return f"{value}{NBSP}{currency.symbol}"
        return f"{currency.symbol}{NBSP}{value}"

    def _chatter_format_number(self, number):
        """Quantity or percentage without useless trailing zeros (1.0 -> 1)."""
        lang = get_lang(self.env)
        value = formatLang(self.env, number, digits=6)
        if lang.decimal_point in value:
            value = value.rstrip("0").rstrip(lang.decimal_point)
        return value

    def _chatter_format_value(self, fname):
        """Readable value of field ``fname`` on this line, for the chatter."""
        field = self._fields[fname]
        value = self[fname]
        if fname in self._chatter_money_fields or field.type == "monetary":
            return self._chatter_format_money(value or 0.0)
        if field.type in ("many2one", "one2many", "many2many"):
            return ", ".join(value.mapped("display_name"))
        if field.type == "float":
            return self._chatter_format_number(value or 0.0)
        if field.type == "boolean":
            return _("Yes") if value else _("No")
        if not value and field.type != "integer":
            return ""
        if field.type == "date":
            return format_date(self.env, value)
        if field.type == "datetime":
            return format_datetime(self.env, value)
        if field.type == "selection":
            return dict(field._description_selection(self.env)).get(value, value)
        return str(value)

    def _chatter_line(self, label, value):
        return Markup("<li>%s</li>") % _("%(label)s: %(value)s", label=label, value=value)

    def _generate_chatter(self, vals, operation):
        if len(self) != 1 or not self.product_tmpl_id:
            return
        name = self.product_id.name or self.product_tmpl_id.name
        if operation == "modified":
            header = _("Price modified for %(product)s", product=name)
        else:
            header = _("Price %(operation)s for %(product)s", operation=operation, product=name)
        msg = Markup(
            "<a href='#' data-oe-model='product.supplierinfo' data-oe-id='%s'>%s</a>"
        ) % (self.id, header)
        context_lines = []
        if self.min_qty > 0:
            context_lines.append(
                self._chatter_line(_("Minimum qty"), self._chatter_format_number(self.min_qty))
            )
        if self.date_start:
            context_lines.append(
                self._chatter_line(_("Starting"), format_date(self.env, self.date_start))
            )
        if self.date_end:
            context_lines.append(
                self._chatter_line(_("Ending"), format_date(self.env, self.date_end))
            )
        if context_lines:
            msg += Markup("<ul>%s</ul>") % Markup().join(context_lines)
        change_lines = []
        for fname in vals:
            field = self._fields.get(fname)
            if field is None:
                continue
            label = field.get_description(self.env)["string"]
            change_lines.append(self._chatter_line(label, self._chatter_format_value(fname)))
        if change_lines:
            msg += Markup("<ul>%s</ul>") % Markup().join(change_lines)
        # Should always be there
        self.product_tmpl_id.message_post(body=msg)
        # only for variant
        if self.product_id:
            self.product_id.message_post(body=msg)

    def write(self, vals):
        res = super(ProductSupplierInfo, self).write(vals)
        self._generate_chatter(vals, "modified")
        return res

    def supplierinfo_show_details(self):
        """
        Action to open product.supplierinfo (pricelist) in its own windows and not in a javascript
        popup to avoid loosing product_tmpl_id.  We rely on both context and domain to pass the
        information
        """
        return {
            "name": "Supplier price",
            "view_type": "form",
            "view_mode": "form",
            "res_id": self.id,
            "context": self.env.context,
            "res_model": "product.supplierinfo",
            "domain": [
                ("product_tmpl_id", "=", self.product_tmpl_id.id),
                ("product_id", "=", self.product_id.id if self.product_id else False),
            ],
            "type": "ir.actions.act_window",
        }
