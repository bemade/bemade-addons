from odoo import Command
from odoo.addons.mail.tests.common import MailCommon

TEMPLATE_A = (
    "<p>{{name}}</p><p>{{job_title}}</p><p>Tél : {{work_phone}}</p>"
    "<p>Cell : {{mobile_phone}}</p><p>{{work_email}}</p><p>{{company_name}}</p>"
)


class CompanySignatureCommon(MailCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.company
        cls.company_b = cls.env["res.company"].create({"name": "Pneumac Test"})
        cls.company_a.sudo().company_signature_template = TEMPLATE_A
        cls.u_full = cls._make_user(
            "sig_full",
            cls.company_a,
            emp={
                "job_title": "Intégrateur",
                "work_phone": "514-555-0100 poste 12",
                "mobile_phone": "514-555-0199",
                "work_email": "full@example.com",
            },
        )
        cls.u_nomobile = cls._make_user(
            "sig_nomobile",
            cls.company_a,
            emp={"job_title": "Technicien", "work_phone": "514-555-0101"},
        )
        cls.u_noemp = cls._make_user("sig_noemp", cls.company_a)
        cls.u_portal = cls.env["res.users"].create(
            {
                "name": "Sig portal",
                "login": "sig_portal",
                "email": "sig_portal@example.com",
                "company_id": cls.company_a.id,
                "company_ids": [Command.set(cls.company_a.ids)],
                "group_ids": [Command.set(cls.env.ref("base.group_portal").ids)],
                "signature": "<p>Perso Sig portal</p>",
            }
        )
        cls.u_b = cls._make_user(
            "sig_b",
            cls.company_b,
            emp={"job_title": "Opérateur", "work_phone": "450-555-0000"},
        )
        cls.all_users = cls.u_full | cls.u_nomobile | cls.u_noemp | cls.u_portal | cls.u_b

    @classmethod
    def _make_user(cls, login, company, emp=None):
        user = cls.env["res.users"].create(
            {
                "name": "Sig %s" % login,
                "login": login,
                "email": "%s@example.com" % login,
                "tz": "America/Montreal",
                "company_id": company.id,
                "company_ids": [Command.set(company.ids)],
                "group_ids": [
                    Command.set(
                        (
                            cls.env.ref("base.group_user")
                            | cls.env.ref("base.group_partner_manager")
                        ).ids
                    )
                ],
                "signature": "<p>Perso %s</p>" % login,
            }
        )
        # hr may auto-create nothing; make sure the employee set is exactly ours
        cls.env["hr.employee"].sudo().search([("user_id", "=", user.id)]).unlink()
        if emp is not None:
            cls._make_employee(user, company, emp)
        return user

    @classmethod
    def _make_employee(cls, user, company, vals=None):
        vals = dict(vals or {})
        return cls.env["hr.employee"].sudo().create(
            {"name": user.name, "user_id": user.id, "company_id": company.id, **vals}
        )

    def _enable(self, company=None, enabled=True):
        company = company or self.company_a
        company.sudo().company_signature_enforced = enabled
        self.env.flush_all()
        self.env.invalidate_all()

    def _employee(self, user):
        return self.env["hr.employee"].sudo().search([("user_id", "=", user.id)], limit=1)
