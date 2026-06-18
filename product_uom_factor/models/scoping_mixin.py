# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.misc import str2bool

_ENFORCE_KEY = "product_uom_factor.enforce_factor_uom_scoping"


class ProductUomFactorLineMixin(models.AbstractModel):
    """Mixin for order/move lines that carry a (product, uom) pair.

    Provides:

    - ``_compute_allowed_uom_ids``: a super-extending compute that only does
      work when no parent class already provides it (i.e. effectively only
      ``mrp.bom.line``, which has no core ``allowed_uom_ids`` compute).  For
      every other target model (``sale.order.line``, ``purchase.order.line``,
      ``stock.move``, ``stock.move.line``, ``account.move.line``) the core
      compute already reads ``product_id.uom_id | product_id.uom_ids``, so the
      factor-specific delegate UoMs reach the allowed list through
      ``product.uom_ids`` (additive template sync) without any extra union.
    - ``_get_factor_uom_ids``: helper that returns the product's delegated
      factor UoMs.  Still used by ``_check_factor_uom_allowed``; **not** unioned
      into ``allowed_uom_ids`` — the delegate is already in ``product.uom_ids``.
    - ``_check_factor_uom_allowed(uom_field_name)``: raises a clear
      ``ValidationError`` if the line's chosen UoM is genuinely cross-tree and
      not one of the product's factor delegates, **unless** the
      ``product_uom_factor.enforce_factor_uom_scoping`` ir.config_parameter is
      set to ``False`` (defaults to ``True``).

    Toggle behaviour
    ----------------
    When ``enforce_factor_uom_scoping = True`` (default):
      - ``_check_factor_uom_allowed`` raises ``ValidationError`` for any
        cross-tree UoM that is not one of the product's factor delegates.
      - The domain on UoM selector fields restricts choices to the product's
        allowed set (``product_id.uom_id | product_id.uom_ids``).

    When ``enforce_factor_uom_scoping = False``:
      - ``_check_factor_uom_allowed`` is a no-op — lines save with any UoM
        (vanilla Odoo behaviour).
      - The UoM field domain is relaxed: no restriction is applied by this
        module (core domains still apply where the model has them).

    This mixin deliberately does NOT declare an ``@api.constrains`` itself,
    because the consuming models use different UoM field names
    (``product_uom_id`` on most lines, ``product_uom`` on ``stock.move``).
    Each ``_inherit`` stub declares its own ``@api.constrains`` referencing the
    correct field name and delegates to ``_check_factor_uom_allowed``.
    """

    _name = "product.uom.factor.line.mixin"
    _description = "Product UoM Factor Line Mixin"

    # Declared here so mrp.bom.line (which inherits the mixin) has the field.
    # Models that already define allowed_uom_ids in core (sale, purchase, stock,
    # account) have the field from there; this declaration is a no-op for them.
    allowed_uom_ids = fields.Many2many("uom.uom", compute="_compute_allowed_uom_ids")

    @api.depends("product_id", "product_id.uom_id", "product_id.uom_ids")
    def _compute_allowed_uom_ids(self):
        """Super-extending compute for allowed_uom_ids.

        Delegates to the parent compute if one exists (sale, purchase, stock.*,
        account.move.line all have one that reads product_id.uom_id |
        product_id.uom_ids — factor delegates ride in via uom_ids, no explicit
        union needed).

        For models with no parent compute (effectively only mrp.bom.line) we
        mirror core's pattern: product_id.uom_id | product_id.uom_ids.
        """
        parent = getattr(super(), "_compute_allowed_uom_ids", None)
        if parent:
            parent()
            return
        # No parent compute — provide the standard set (factor delegates are
        # already in product.uom_ids via the additive template sync).
        for line in self:
            product = line.product_id
            if not product:
                line.allowed_uom_ids = self.env["uom.uom"]
            else:
                line.allowed_uom_ids = product.uom_id | product.uom_ids

    def _get_factor_uom_ids(self):
        """Return the product's factor-specific delegated UoMs.

        Used by ``_check_factor_uom_allowed`` to validate cross-tree UoM
        selections.  Not unioned into ``allowed_uom_ids`` — the delegates reach
        the allowed list through ``product.uom_ids`` (additive template sync).
        """
        product = getattr(self, "product_id", False) or getattr(
            self, "product_tmpl_id", False
        )
        if not product:
            return self.env["uom.uom"]
        if product._name == "product.template":
            tmpl = product
        else:
            tmpl = product.product_tmpl_id
        return tmpl.uom_factor_ids.mapped("delegate_uom_id")

    def _is_factor_uom_scoping_enforced(self):
        """Return True when the scoping constraint is active (default).

        Reads ``ir.config_parameter`` once per constraint batch call.  The
        parameter stores a string "True" / "False"; absent param = True
        (default-on).
        """
        raw = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(_ENFORCE_KEY, default="True")
        )
        return str2bool(raw, True)

    def _check_factor_uom_allowed(self, uom_field_name):
        """Raise if the line's chosen UoM is not in the product's allowed set.

        No-ops immediately when ``enforce_factor_uom_scoping`` is False so that
        cross-tree UoM selections are permitted (vanilla Odoo behaviour).

        :param uom_field_name: the name of the UoM field on the consuming model
            (e.g. ``"product_uom_id"`` or ``"product_uom"``).
        """
        if not self._is_factor_uom_scoping_enforced():
            return
        for rec in self:
            product = getattr(rec, "product_id", False)
            product_uom = getattr(rec, uom_field_name, False)
            if not product or not product_uom:
                continue
            base_uom = product.uom_id
            if not base_uom:
                continue
            # Same-category (common-reference) UoMs are always fine: native
            # Odoo converts them correctly. We only police genuinely cross-tree
            # UoMs, which MUST be one of the product's factor delegates.
            if base_uom._has_common_reference(product_uom):
                continue
            # For cross-tree units, check they are a factor delegate for this
            # product. The delegate is in product.uom_ids (via additive sync),
            # so checking uom_ids is equivalent — but _get_factor_uom_ids is
            # more precise for the error message (lists only factor UoMs).
            factor_uoms = rec._get_factor_uom_ids()
            if product_uom not in factor_uoms:
                allowed = product.uom_ids | factor_uoms
                raise ValidationError(
                    rec.env._(
                        "Unit of measure '%(uom)s' is not allowed for product "
                        "'%(product)s': it is in a different unit tree and is not "
                        "one of the product's cross-category conversion factors. "
                        "Add a conversion factor for this unit on the product "
                        "form, or pick one of: %(allowed)s.",
                        uom=product_uom.name,
                        product=product.display_name,
                        allowed=", ".join(
                            (base_uom | allowed).mapped("name")
                        ),
                    )
                )
