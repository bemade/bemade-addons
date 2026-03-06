import logging
from odoo import models, api, _

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def button_validate(self):
        res = super().button_validate()
        for picking in self:
            if picking.carrier_tracking_ref:
                picking._notify_tracking_number()
        return res

    def _notify_tracking_number(self):
        """Post a notification to the sale order when tracking number is set."""
        self.ensure_one()

        # Only process outgoing pickings with tracking numbers and linked to a sale order
        if (
            self.picking_type_code != "outgoing"
            or not self.carrier_tracking_ref
            or not self.sale_id
        ):
            return

        # Get the mail template
        template = self.env.ref(
            "delivery_notification.mail_template_tracking_notification",
            raise_if_not_found=False,
        )
        if not template:
            _logger.error(
                "Mail template 'mail_template_tracking_notification' not found"
            )
            return

        # Build tracking URL if available
        tracking_url = None
        if self.carrier_id:
            try:
                # Try to get tracking URL using the carrier's method
                if hasattr(self.carrier_id, "get_tracking_link"):
                    tracking_url = self.carrier_id.get_tracking_link(self)
            except Exception as e:
                _logger.warning(
                    "Failed to get tracking link for picking %s: %s", self.name, str(e)
                )

        # Render the template with context in partner's language
        # Template uses lang field to compute language from sale order partner
        message_body = template._render_field(
            "body_html",
            self.sale_id.ids,
            compute_lang=True,
            add_context={
                "tracking_ref": self.carrier_tracking_ref,
                "tracking_url": tracking_url,
            },
        )[self.sale_id.id]

        # Post the message to the sales order with custom subtype
        # This will notify all followers (customer if they have email, and internal users)
        self.sale_id.message_post(
            body=message_body,
            subject=template.subject or _("Shipment Tracking Information"),
            message_type="notification",
            subtype_xmlid="delivery_notification.mt_tracking_number_set",
        )
