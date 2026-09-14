from odoo import _, http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request
from odoo.addons.sale.controllers.portal import CustomerPortal
from odoo.addons.portal.controllers.portal import pager as portal_pager


class CustomerPortalInherit(CustomerPortal):

    def _prepare_quotations_domain(self, partner):
        domain = super()._prepare_quotations_domain(partner)
        return domain

    def _prepare_sale_portal_rendering_values(
        self,
        page=1,
        date_begin=None,
        date_end=None,
        sortby=None,
        quotation_page=False,
        **kwargs
    ):
        values = super()._prepare_sale_portal_rendering_values(
            page=page,
            date_begin=date_begin,
            date_end=date_end,
            sortby=sortby,
            quotation_page=quotation_page,
            **kwargs,
        )
        values["enforce_customer_reference"] = (
            request.env["ir.config_parameter"]
            .sudo()
            .get_param(
                "sale_mandatory_customer_reference.enforce_customer_reference", False
            )
        )
        return values

    @http.route(
        ["/my/orders/<int:order_id>/accept"], type="json", auth="public", website=True
    )
    def portal_quote_accept(
        self, order_id, access_token=None, name=None, signature=None
    ):
        """Refuse cleanly when the mandatory reference is missing.

        The portal SignatureForm has no error handling around its RPC: an
        exception raised by action_confirm leaves the button spinning forever.
        Return the message as ``{'error': ...}`` *before* the signature is
        written so the form displays it and re-enables the button.
        """
        access_token = access_token or request.httprequest.args.get("access_token")
        try:
            order_sudo = self._document_check_access(
                "sale.order", order_id, access_token=access_token
            )
        except (AccessError, MissingError):
            return {"error": _("Invalid order.")}

        if (
            order_sudo._get_enforce_customer_reference()
            and not order_sudo.client_order_ref
            # a paid order is confirmed after payment, where the reference
            # falls back to "Credit Card"
            and not order_sudo._has_to_be_paid()
        ):
            return {"error": order_sudo._get_missing_customer_reference_message()}

        return super().portal_quote_accept(
            order_id, access_token=access_token, name=name, signature=signature
        )

    @http.route(
        ["/my/orders/<int:order_id>/update_reference"],
        type="json",
        auth="public",
        website=True,
    )
    def portal_update_sale_reference(
        self, order_id, reference, access_token=None, **kw
    ):
        try:
            order_sudo = self._document_check_access(
                "sale.order", order_id, access_token=access_token
            )
        except (AccessError, MissingError):
            return {"error": _("Access Denied")}

        if order_sudo.state not in ("draft", "sent"):
            return {"error": _("Order cannot be modified in its current state")}

        order_sudo.write({"client_order_ref": reference})
        return {"success": True}
