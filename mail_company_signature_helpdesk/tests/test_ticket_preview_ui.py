"""Use case: on a ticket, the composer previews the signature that goes out.

Acceptance criteria:
- AC1: the chatter « Send message » preview shows the team address, not the
  agent's personal address.
- AC2: the full composer opened from it inserts the same signature.
"""

from odoo.tests import HttpCase, tagged

from .common import TicketSenderCommon


@tagged("post_install", "-at_install")
class TestTicketPreviewUI(HttpCase, TicketSenderCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tour_agent = cls._agent("Desk Tour", "desk_tour", "desk.agent@example.org", password="desk_tour")
        cls.team.mail_send_as_alias_id = cls.sac_alias
        cls.company.sudo().company_signature_enforced = True
        cls._grant_ticket_form_read_access(cls.tour_agent)

    @classmethod
    def _grant_ticket_form_read_access(cls, user):
        """Other addons add fields to the ticket form whose comodel the
        minimal tour user cannot read: grant read so the form renders (the
        tour tests the composer, not those ACLs)."""
        group = cls.env.ref("base.group_user")
        user_env = cls.env(user=user)
        for field in cls.env["helpdesk.ticket"]._fields.values():
            comodel = getattr(field, "comodel_name", None)
            if not comodel or comodel not in cls.env or user_env[comodel].has_access("read"):
                continue
            cls.env["ir.model.access"].create(
                {
                    "name": "mail_company_signature_helpdesk tour read %s" % comodel,
                    "model_id": cls.env["ir.model"]._get_id(comodel),
                    "group_id": group.id,
                    "perm_read": True,
                }
            )

    def test_preview_shows_team_address(self):
        self.start_tour(
            "/odoo/helpdesk.ticket/%s" % self.ticket.id,
            "mail_company_signature_helpdesk_preview",
            login="desk_tour",
        )
