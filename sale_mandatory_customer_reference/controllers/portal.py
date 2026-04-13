from odoo import http
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
        ["/my/orders/<int:order_id>/update_reference"],
        type="json",
        auth="public",
        website=True,
    )
    def portal_update_sale_reference(
        self, order_id, reference, access_token=None, **kw
    ):
        try:
            order = request.env["sale.order"].browse(order_id)
            if not order.exists():
                return {"error": "Order not found"}

            # Try user access first
            try:
                # These will raise if access denied
                order.check_access_rights("write")
                order.check_access_rule("write")
            except Exception:
                # If user access fails, try token access
                if access_token:
                    order = request.env["sale.order"].sudo().browse(order_id)
                    try:
                        order.check_access_token(access_token)
                    except Exception:
                        return {"error": "Access Denied"}
                else:
                    return {"error": "Access Denied"}

            if order.state not in ("draft", "sent"):
                return {"error": "Order cannot be modified in its current state"}

            order.write({"client_order_ref": reference})
            return {"success": True}

        except Exception as e:
            return {"error": str(e)}
