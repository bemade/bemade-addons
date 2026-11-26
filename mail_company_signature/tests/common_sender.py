"""Fixtures for the sending-address tests (all synthetic)."""

import re
from contextlib import contextmanager
from unittest.mock import patch

from markupsafe import Markup

from .common import CompanySignatureCommon


class SenderCommon(CompanySignatureCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        IrModel = cls.env["ir.model"]
        cls.external = cls.env["res.partner"].create(
            {"name": "Sender Supplier", "email": "sender.supplier@example.com"}
        )
        cls.team_record = cls.env["hr.department"].create({"name": "Purchasing Team"})
        cls.document = cls.env["res.partner"].create(
            {"name": "Sender Document", "company_id": cls.company_a.id}
        )
        # A team inbox: an alias creating other records (here job positions),
        # owned by a team record (its name is the label in From).
        cls.alias = cls.env["mail.alias"].create(
            {
                "alias_name": "purchasing-test",
                "alias_domain_id": cls.mail_alias_domain.id,
                "alias_model_id": IrModel._get_id("hr.job"),
                "alias_parent_model_id": IrModel._get_id("hr.department"),
                "alias_parent_thread_id": cls.team_record.id,
            }
        )
        cls.alias_email = "purchasing-test@%s" % cls.alias_domain
        cls.override_email = "care-test@%s" % cls.alias_domain
        cls.fixed_from = "buying-desk@%s" % cls.alias_domain

    def setUp(self):
        super().setUp()
        self.env.invalidate_all()

    def _set_alias(self, user, alias):
        user.sudo().mail_send_as_alias_id = alias
        self.env.flush_all()

    def _setting(self, enabled=True, company=None):
        (company or self.company_a).sudo().mail_send_from_signature_address = enabled
        self.env.flush_all()

    @contextmanager
    def _record_override(self, email=None, label="Care Test", model="res.partner"):
        """Make ``model`` impose an address, like a helpdesk ticket."""
        email = email or self.override_email
        Department = type(self.env[model])

        def override(record, user):
            return {"email": email, "label": label}

        with patch.object(Department, "_mail_sender_override", override, create=True):
            yield

    def _post(self, user, record=None, **kwargs):
        record = record or self.document
        kwargs.setdefault("body", Markup("<p>Bonjour</p>"))
        with self.mock_mail_gateway():
            message = record.with_user(user).message_post(
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
                partner_ids=self.external.ids,
                **kwargs,
            )
            self.env.flush_all()
        mail = self._new_mails.filtered(lambda m: self.external in m.recipient_ids)
        self.assertEqual(len(mail), 1)
        return message, mail

    def _template(self, body_html, email_from="{{ user.email_formatted }}", model="res.partner"):
        return self.env["mail.template"].create(
            {
                "name": "Sender template",
                "model_id": self.env["ir.model"]._get_id(model),
                "subject": "Your document",
                "body_html": body_html,
                "email_from": email_from,
                "email_to": self.external.email,
                "use_default_to": False,
            }
        )

    def _send_template(self, template, user, record=None):
        record = record or self.document
        with self.mock_mail_gateway():
            mail_id = template.with_user(user).send_mail(record.id)
            self.env.flush_all()
        return self.env["mail.mail"].sudo().browse(mail_id)

    @staticmethod
    def _signature_part(html, start_text):
        """The signature and what follows it. Sibling addons may print the
        author's address in a header above the body, so the checks look at
        the signature fragment only."""
        html = str(html)
        start = html.find(start_text)
        return html[start:] if start >= 0 else ""

    def assertMentions(self, html, email):
        self.assertTrue(self._mentions(html, email), "%s not in %s" % (email, html))

    def assertNotMentions(self, html, email):
        self.assertFalse(self._mentions(html, email), "%s in %s" % (email, html))

    @staticmethod
    def _mentions(html, email):
        """Whole-address match (``full@`` is not ``sig_full@``)."""
        return bool(re.search(r"(?<![\w.+-])%s(?![\w-])" % re.escape(email), str(html), re.I))
