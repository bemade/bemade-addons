import textwrap

from lxml import etree, html

from odoo import models
from odoo.tools.mail import html_to_inner_content

from .mail_thread import SIGNATURE_CLASS


class MailMessage(models.Model):
    _inherit = "mail.message"

    def _compute_preview(self):
        """Keep the signature block out of the preview (inbox lists, the hidden
        pre-header of the email): it shows the message, not who signed it."""
        res = super()._compute_preview()
        for message in self:
            body = message.body
            if not body or SIGNATURE_CLASS not in body:
                continue
            try:
                root = html.fragment_fromstring(str(body), create_parent="div")
            except (etree.ParserError, ValueError):
                continue
            for block in root.xpath(
                "//*[contains(concat(' ', normalize-space(@class), ' '), ' %s ')]"
                % SIGNATURE_CLASS
            ):
                block.drop_tree()
            text = html_to_inner_content(etree.tostring(root, encoding="unicode"))
            message.preview = textwrap.shorten(text, 190)
        return res
