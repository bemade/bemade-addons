import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    def _notify_get_recipients(self, message, msg_vals=False, **kwargs):
        recipients = super()._notify_get_recipients(message, msg_vals=msg_vals, **kwargs)

        now = fields.Datetime.now()
        recipient_partner_ids = {r["id"] for r in recipients}

        for recipient in list(recipients):
            user = self.env["res.users"].search(
                [("partner_id", "=", recipient["id"])], limit=1
            )
            if not user:
                continue
            employee = self.env["hr.employee"].search(
                [("user_id", "=", user.id)], limit=1
            )
            if not employee:
                continue

            leaves = self.sudo().env["hr.leave"].search([
                ("state", "=", "validate"),
                ("date_from", "<=", now),
                ("date_to", ">", now),
                ("employee_id", "=", employee.id),
            ])
            for leave in leaves:
                if not leave.alternate_follower_id:
                    continue
                alt_partner = leave.alternate_follower_id.partner_id
                if alt_partner.id in recipient_partner_ids:
                    continue

                alt_user = leave.alternate_follower_id
                _logger.info(
                    "Adding %s as alternate follower for %s while on time off.",
                    alt_partner.name, employee.name,
                )
                recipients.append({
                    "id": alt_partner.id,
                    "active": alt_partner.active,
                    "email_normalized": alt_partner.email_normalized,
                    "is_follower": False,
                    "lang": alt_partner.lang,
                    "name": alt_partner.name,
                    "share": alt_partner.partner_share,
                    "groups": alt_user.group_ids.ids,
                    "notif": alt_user.notification_type or "inbox",
                    "type": "user",
                    "uid": alt_user.id,
                    "ushare": all(u.share for u in alt_partner.user_ids) if alt_partner.user_ids else False,
                })
                recipient_partner_ids.add(alt_partner.id)

        return recipients
