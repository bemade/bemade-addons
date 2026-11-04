from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    @api.model
    def _activity_done_lang_selection(self):
        return self.env["res.lang"].get_installed()

    activity_done_lang = fields.Selection(
        selection="_activity_done_lang_selection",
        string="Language of activity completion messages",
        help="Language of the message posted in the chatter when an activity is "
        "marked as done. Empty: the language of the user marking it as done.",
    )
