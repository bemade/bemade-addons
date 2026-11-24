from odoo.tests import TransactionCase


class EmailDomainCase(TransactionCase):
    """Synthetic companies on reserved/fictional domains only."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env["res.partner"]
        cls.Suggestion = cls.env["partner.parent.suggestion"]
        cls.env["ir.config_parameter"].sudo().set_param("bemade_partner_email_domain.suggest_only", False)

    @classmethod
    def _company(cls, name, domain, **vals):
        return cls.Partner.create(dict({"name": name, "is_company": True, "email_domain": domain}, **vals))

    def _contact(self, email, **vals):
        return self.Partner.create(dict({"name": "Test Contact", "email": email}, **vals))

    def _rows(self, partner):
        return self.Suggestion.search([("partner_id", "=", partner.id)])
