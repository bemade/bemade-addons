from odoo import Command

from odoo.addons.mail.tests.common import MailCommon

TEMPLATE = "<p>{{name}}</p><p>{{job_title}}</p><p>Courriel : {{work_email}}</p>"


class TicketSenderCommon(MailCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.sudo().company_signature_template = TEMPLATE
        cls.agent = cls._agent("Desk Agent", "desk_agent", "desk.agent@example.com")
        cls.agent_sendas = cls._agent("Desk Buyer", "desk_buyer", "desk.buyer@example.com")
        cls.customer = cls.env["res.partner"].create(
            {"name": "Desk Customer", "email": "desk.customer@example.com"}
        )
        Team = cls.env["helpdesk.team"].with_context(mail_create_nosubscribe=True)
        cls.team = Team.create(
            {
                "name": "Care Test",
                "use_alias": True,
                "alias_name": "care-test",
                "alias_domain_id": cls.mail_alias_domain.id,
            }
        )
        cls.other_team = Team.create(
            {
                "name": "Buying Test",
                "use_alias": True,
                "alias_name": "buying-test",
                "alias_domain_id": cls.mail_alias_domain.id,
            }
        )
        cls.no_alias_team = Team.create({"name": "Quiet Test", "use_alias": False})
        cls.no_alias_team.alias_name = False
        IrModel = cls.env["ir.model"]
        cls.sac_alias = cls.env["mail.alias"].create(
            {
                "alias_name": "sac-test",
                "alias_domain_id": cls.mail_alias_domain.id,
                "alias_model_id": IrModel._get_id("helpdesk.ticket"),
                "alias_parent_model_id": IrModel._get_id("helpdesk.team"),
                "alias_parent_thread_id": cls.team.id,
                "alias_defaults": "{'team_id': %s}" % cls.team.id,
            }
        )
        cls.sac_email = "sac-test@%s" % cls.alias_domain
        cls.care_email = "care-test@%s" % cls.alias_domain
        cls.buying_email = "buying-test@%s" % cls.alias_domain
        cls.agent_sendas.mail_send_as_alias_id = cls.other_team.alias_id
        cls.ticket = cls.env["helpdesk.ticket"].create(
            {"name": "Desk ticket", "team_id": cls.team.id, "partner_id": cls.customer.id}
        )

    @classmethod
    def _agent(cls, name, login, email, password=None):
        groups = (
            cls.env.ref("base.group_user")
            | cls.env.ref("base.group_partner_manager")
            | cls.env.ref("helpdesk.group_helpdesk_user")
        ).ids
        vals = {
            "name": name,
            "login": login,
            "email": email,
            "company_id": cls.env.company.id,
            "company_ids": [Command.set(cls.env.company.ids)],
            "group_ids": [Command.set(groups)],
        }
        if password:
            vals["password"] = password
        user = cls.env["res.users"].create(vals)
        cls.env["hr.employee"].sudo().search([("user_id", "=", user.id)]).unlink()
        cls.env["hr.employee"].sudo().create(
            {
                "name": name,
                "user_id": user.id,
                "company_id": cls.env.company.id,
                "job_title": "Conseiller",
                "work_email": email,
            }
        )
        return user

    def _enable_policy(self, enabled=True):
        self.company.sudo().company_signature_enforced = enabled
        self.env.flush_all()
        self.env.invalidate_all()
