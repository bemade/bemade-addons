from odoo import models


class MailActivity(models.Model):
    _inherit = "mail.activity"

    def _action_done(self, feedback=False, attachment_ids=None):
        # The "done" message is rendered once, in the context language; a
        # company can force that language for every closer.
        lang = self.env.company.activity_done_lang
        if lang:
            self = self.with_context(lang=lang)
        return super()._action_done(feedback=feedback, attachment_ids=attachment_ids)
