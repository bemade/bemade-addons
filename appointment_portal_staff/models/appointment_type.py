# Part of Appointment Portal Staff. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class AppointmentType(models.Model):
    _inherit = 'appointment.type'

    # Lift the stock "[('share', '=', False)]" domain so portal (share)
    # users can be selected as appointment staff. No python constraint
    # blocks the assignment itself and the stock backend views do not
    # repeat the domain, so no view override is needed. At BOOKING time,
    # the enterprise booking-line constraint
    # `_check_user_or_resource_match_appointment_type` additionally
    # requires the staff user to have read access to the appointment type
    # — granted for their own types by this module's security files.
    staff_user_ids = fields.Many2many(domain=[])
