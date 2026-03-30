import base64
import logging
from odoo import models, api, _
from odoo.tools.misc import get_lang

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def button_validate(self):
        res = super().button_validate()
        for picking in self:
            if picking.state == "done" and picking.carrier_tracking_ref:
                picking._notify_tracking_number()
        return res

    def _get_order_contact_partner(self):
        """Get the contact that placed the order.

        Returns the partner record of the order contact:
        - If the order was created by a portal user, return their partner
        - Otherwise, return the sale order's partner_id
        """
        self.ensure_one()
        sale_order = self.sale_id

        if not sale_order:
            return False

        # Default to the sale order's customer
        recipient_partner = sale_order.partner_id

        # Check if the order was created by a portal user (external contact)
        # In Odoo, create_uid is the user who created the record
        if sale_order.create_uid:
            creator = sale_order.create_uid
            # Check if creator is a portal user (has a partner, not internal user)
            if creator.partner_id and creator.partner_id != self.env.ref('base.partner_root'):
                creator_partner = creator.partner_id
                # If creator is a child of the customer's company, use them
                if creator_partner.parent_id:
                    if creator_partner.parent_id == sale_order.partner_id:
                        recipient_partner = creator_partner
                # If creator is the customer themselves
                elif creator_partner == sale_order.partner_id:
                    recipient_partner = creator_partner

        return recipient_partner

    def _notify_tracking_number(self):
        """Send an email notification when tracking number is set.

        Recipients depend on company setting:
        - 'followers': All followers of the sale order (Odoo default behavior)
        - 'order_contact': Only the contact who placed the order
        """
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

        # Render the message body
        body = template._render_field(
            "body_html",
            self.sale_id.ids,
            compute_lang=True,
            add_context={
                "tracking_ref": self.carrier_tracking_ref,
                "tracking_url": tracking_url,
            },
        )[self.sale_id.id]

        # Generate delivery order PDF attachment
        attachments = []
        try:
            report = self.env.ref('stock.action_report_delivery', raise_if_not_found=False)
            if report:
                pdf_content, _ = report._render(self.ids)
                attachment = self.env['ir.attachment'].create({
                    'name': f"Delivery_Order_{self.name}.pdf",
                    'type': 'binary',
                    'datas': base64.b64encode(pdf_content),
                    'res_model': 'stock.picking',
                    'res_id': self.id,
                    'mimetype': 'application/pdf',
                })
                attachments.append(attachment.id)
        except Exception as e:
            _logger.warning(
                "Failed to generate delivery PDF for picking %s: %s",
                self.name,
                str(e),
            )

        # Determine recipients based on company setting
        company = self.sale_id.company_id or self.env.company
        recipient_mode = company.delivery_notification_recipient

        # Post message to the sale order
        message_kwargs = {
            "body": body,
            "subject": template.subject or _("Shipment Tracking Information"),
            "message_type": "comment",
            "subtype_xmlid": "mail.mt_comment",  # External message, will send email
        }
        if attachments:
            message_kwargs["attachment_ids"] = [(6, 0, attachments)]

        if recipient_mode == "order_contact":
            # Send only to the contact that placed the order
            recipient_partner = self._get_order_contact_partner()
            if not recipient_partner:
                _logger.warning(
                    "No recipient partner found for picking %s",
                    self.name,
                )
                return
            if not recipient_partner.email:
                _logger.warning(
                    "No email address found for recipient partner %s on sale order %s",
                    recipient_partner.name,
                    self.sale_id.name,
                )
                return
            message_kwargs["partner_ids"] = [recipient_partner.id]

        # For 'followers' mode, omit partner_ids so all followers receive the notification
        self.sale_id.message_post(**message_kwargs)