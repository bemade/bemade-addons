from odoo import api, models
from odoo.fields import Domain

# Customer code fields the displayed name and reference depend on.
_CODE_DEPENDS = (
    "product_tmpl_id.product_customer_code_ids.product_code",
    "product_tmpl_id.product_customer_code_ids.product_name",
    "product_tmpl_id.product_customer_code_ids.partner_id",
    "product_tmpl_id.product_customer_code_ids.active",
)
# Context keys core's display_name depends on; an override must restate them.
_DISPLAY_NAME_CONTEXT = (
    "display_default_code",
    "seller_id",
    "company_id",
    "partner_id",
    "formatted_display_name",
    "lang",
)


class ProductProduct(models.Model):
    _inherit = "product.product"

    # ------------------------------------------------------------------
    # Customer code lookup
    # ------------------------------------------------------------------

    def _context_partner(self):
        return self.env["res.partner"].browse(self.env.context.get("partner_id") or [])

    def _get_customer_codes(self, partner):
        """Return ``{product: product.customer.code}`` for ``partner``.

        A code recorded on the partner itself wins over one recorded on its
        commercial partner. Products without a code are left out.
        """
        if not partner or not self:
            return {}
        partners = partner | partner.commercial_partner_id
        codes = (
            self.env["product.customer.code"]
            .sudo()
            .search(
                [
                    ("product_id", "in", self.product_tmpl_id.ids),
                    ("partner_id", "in", partners.ids),
                    ("company_id", "in", [False, *self.env.companies.ids]),
                ]
            )
        )
        # The partner's own codes come last so they overwrite the company's.
        by_template = {
            code.product_id: code
            for code in codes.sorted(lambda code: code.partner_id == partner)
        }
        return {
            product: by_template[product.product_tmpl_id]
            for product in self
            if product.product_tmpl_id in by_template
        }

    def has_customer_code(self, partner):
        """Whether ``partner`` (or its commercial partner) has a code on one of
        these products."""
        return bool(self._get_customer_codes(partner))

    def _get_partner_code_name(self, product, partner):
        """Return ``{"code", "name"}`` for ``product`` as ``partner`` knows it,
        each falling back to the product's own internal reference and name."""
        code = product._get_customer_codes(partner).get(product)
        return {
            "code": (code and code.product_code) or product.default_code,
            "name": (code and code.product_name) or product.name,
        }

    def _customer_code_name(self, code):
        """``(code, name)`` of this product for a customer code, with the
        variant's attributes appended to the name as standard Odoo does."""
        self.ensure_one()
        name = code.product_name or self.name
        variant = self.product_template_attribute_value_ids._get_combination_name()
        if variant:
            name = f"{name} ({variant})"
        return code.product_code or self.default_code, name

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    @api.depends("name", "default_code", "product_tmpl_id", *_CODE_DEPENDS)
    @api.depends_context(*_DISPLAY_NAME_CONTEXT, "sale_order_mode")
    def _compute_display_name(self):
        super()._compute_display_name()
        context = self.env.context
        if context.get("sale_order_mode") or context.get("seller_id"):
            return
        with_code = context.get("display_default_code", True)
        for product, code in self._get_customer_codes(self._context_partner()).items():
            ref, name = product._customer_code_name(code)
            if not (with_code and ref):
                product.display_name = name
            elif context.get("formatted_display_name"):
                product.display_name = f"{name}\t--{ref}--"
            else:
                product.display_name = f"[{ref}] {name}"

    @api.depends(*_CODE_DEPENDS)
    @api.depends_context("partner_id")
    def _compute_partner_ref(self):
        super()._compute_partner_ref()
        for product, code in self._get_customer_codes(self._context_partner()).items():
            ref, name = product._customer_code_name(code)
            product.partner_ref = f"[{ref}] {name}" if ref else name

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    @api.model
    def _customer_code_domain(self, operator, value):
        """Products having a customer code matching ``value`` (with a positive
        ``operator``), restricted to the context partner's codes if any."""
        code_domain = Domain("product_code", operator, value) | Domain(
            "product_name", operator, value
        )
        partner = self._context_partner()
        if partner:
            partners = partner | partner.commercial_partner_id
            code_domain &= Domain("partner_id", "in", partners.ids)
        return Domain("product_tmpl_id.product_customer_code_ids", "any", code_domain)

    @api.model
    def _search_display_name(self, operator, value):
        domain = Domain(super()._search_display_name(operator, value))
        positive = Domain.NEGATIVE_OPERATORS.get(operator)
        if positive:
            return domain & ~self._customer_code_domain(positive, value)
        return domain | self._customer_code_domain(operator, value)

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        result = super().name_search(name, domain, operator, limit)
        if (
            not name
            or operator in Domain.NEGATIVE_OPERATORS
            or (limit and len(result) >= limit)
        ):
            return result
        extra = self.search_fetch(
            Domain(domain or Domain.TRUE)
            & Domain("id", "not in", [product_id for product_id, _name in result])
            & self._customer_code_domain(operator, name),
            ["display_name"],
            limit=limit and limit - len(result),
        )
        return result + [(product.id, product.display_name) for product in extra.sudo()]
