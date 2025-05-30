# Import necessary modules and classes
from odoo import models, api, fields
import logging

# Set up logging
_logger = logging.getLogger(__name__)


# Define a new class that inherits from 'mail.thread'
class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    # Override the '_notify_get_recipients' method
    def _notify_get_recipients(self, message, msg_vals, **kwargs):
        # Call the parent class's method and get the recipients
        recipients = super(MailThread, self)._notify_get_recipients(
            message, msg_vals, **kwargs
        )

        # Get the current datetime
        now = fields.Datetime.now()
        recipient_partner_ids = [recipient["id"] for recipient in recipients]
        # Loop through each recipient
        for recipient in recipients:
            # Search for a user with the same partner_id as the recipient

            user = self.env["res.users"].search(
                [("partner_id", "=", recipient["id"])], limit=1
            )
            # If a user is found, search for an employee with the same user_id
            if user:
                employee = self.env["hr.employee"].search(
                    [("user_id", "=", user.id)], limit=1
                )
            else:
                employee = False

            # If an employee is found
            if employee:
                employee_id = employee.id
                # Search for leaves that are validated, within the date range, and belong to the employee
                leaves = (
                    self.sudo()
                    .env["hr.leave"]
                    .search(
                        [
                            ("state", "=", "validate"),
                            ("date_from", "<=", now),
                            ("date_to", ">", now),
                            ("employee_id", "=", employee_id),
                        ]
                    )
                )
                # Loop through each leave
                for leave in leaves:
                    # If the leave has an alternate follower and the follower is not already in the recipients list
                    if (
                        leave.alternate_follower_id
                        and leave.alternate_follower_id.partner_id.id not in recipients
                    ):
                        # Log the addition of the alternate follower
                        # Add the alternate follower to the recipients list
                        alternate_follower_id = (
                            leave.alternate_follower_id.partner_id.id)
                        if alternate_follower_id not in recipient_partner_ids:
                            _logger.info(
                                f"Adding {leave.alternate_follower_id.partner_id.name} as follower for {employee.name} "
                                f"while on time off."
                            )
                            recipients.append(
                                {
                                    "id": leave.alternate_follower_id.partner_id.id,
                                    "active": True,
                                    "share": False,
                                    "groups": leave.alternate_follower_id.groups_id.ids,
                                    "notif": "inbox",
                                    "type": "user",
                                }
                            )
                        else:
                            _logger.info(
                                f"{leave.alternate_follower_id.partner_id.name}"
                                f" is already a recipient. Skipping alternate "
                                f"follower addition."
                            )
                    else:
                        _logger.info(
                            f"Not adding {leave.alternate_follower_id.partner_id.name} for {employee.name}, All ready "
                            f"a follower."
                        )

        # Return the updated recipients list
        return recipients
