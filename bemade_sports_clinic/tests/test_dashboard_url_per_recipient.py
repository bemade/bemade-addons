from datetime import timedelta

from odoo import fields
from odoo.fields import Command
from odoo.tests import TransactionCase, tagged


@tagged("-at_install", "post_install")
class TestDashboardUrlPerRecipient(TransactionCase):
    """Task 1396 — the team-dashboard link is chosen PER RECIPIENT.

    Before this task each notification surface hardcoded one link shape:
    urgent alerts always sent the internal backend action URL (wrong for the
    portal coaches/therapists who are the majority of recipients) and the
    morning briefing always sent the portal URL (the mirror bug, wrong for
    internal staff). Both now pick per recipient through the shared
    ``sports.team._dashboard_url`` formatter.

    Acceptance coverage:
      * portal coach's URGENT mail links to ``/my/team?team_id=<id>``;
      * internal staff member's URGENT mail links to the backend action URL;
      * internal staff member's BRIEFING links to the backend action URL;
      * portal coach's BRIEFING still links to the portal URL (unchanged);
      * two recipients of DIFFERENT types on the SAME team, in ONE urgent run,
        each get their own correct link;
      * a partner with NO user at all gets the portal link;
      * a partner with BOTH an active portal and an active internal user gets
        the backend link;
      * an ARCHIVED internal user + an active portal user gets the PORTAL link
        (their internal access is gone);
      * regression — archived users still receive nothing at all on either
        surface, so "only inactive users" never reaches a link decision. That
        eligibility gate (``_is_follower_eligible`` / ``_digest_eligible_users``)
        is deliberately NOT merged with the link decision: it inspects archived
        users to DENY notification, the link decision ignores them to PICK a
        link.

    All fixtures are synthetic.
    """

    BASE_URL = "http://synthetic.test"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Patient = cls.env["sports.patient"]
        cls.Injury = cls.env["sports.patient.injury"]
        cls.Users = cls.env["res.users"]
        cls.ICP = cls.env["ir.config_parameter"].sudo()
        cls.ICP.set_param("web.base.url", cls.BASE_URL)
        cls.ICP.set_param(
            "bemade_sports_clinic.digest_morning_send_time", "00:00"
        )

        cls.portal_group = cls.env.ref("base.group_portal")
        cls.internal_group = cls.env.ref("base.group_user")
        cls.action = cls.env.ref("bemade_sports_clinic.action_view_team")

        cls.org = cls.env["res.partner"].create({
            "name": "Synthetic Org", "is_company": True,
        })
        cls.team = cls.env["sports.team"].create({
            "name": "Alpha Team", "parent_id": cls.org.id,
        })

        # --- recipients, one shape each -------------------------------------
        # Pure contact, never had a login.
        cls.p_contact = cls._partner("contact_only")
        # Active portal user.
        cls.p_portal = cls._partner("portal_coach")
        cls.u_portal = cls._user(cls.p_portal, "portal_coach", share=True)
        # Active internal user.
        cls.p_internal = cls._partner("internal_tp")
        cls.u_internal = cls._user(cls.p_internal, "internal_tp", share=False)
        # BOTH an active portal user and an active internal user.
        cls.p_both = cls._partner("both_kinds")
        cls._user(cls.p_both, "both_portal", share=True)
        cls._user(cls.p_both, "both_internal", share=False)
        # Archived internal user + active portal user.
        cls.p_revoked_internal = cls._partner("revoked_internal")
        cls.u_revoked_portal = cls._user(
            cls.p_revoked_internal, "revoked_still_portal", share=True
        )
        cls.u_revoked_internal = cls._user(
            cls.p_revoked_internal, "revoked_was_internal", share=False
        )
        cls.u_revoked_internal.active = False
        # Only archived users -> never notified at all (regression fixture).
        cls.p_archived_only = cls._partner("archived_only")
        cls.u_archived_only = cls._user(
            cls.p_archived_only, "archived_only", share=True
        )
        cls.u_archived_only.active = False

        cls._staff(cls.p_contact, "coach")
        cls._staff(cls.p_portal, "coach")
        cls._staff(cls.p_internal, "therapist")
        cls._staff(cls.p_both, "coach")
        cls._staff(cls.p_revoked_internal, "coach")
        cls._staff(cls.p_archived_only, "coach")

        cls.patient = cls.Patient.create({
            "first_name": "Synth",
            "last_name": "Player",
            "team_ids": [Command.link(cls.team.id)],
        })
        cls.env.cr.precommit.run()

    # ------------------------------------------------------------------ helpers
    @classmethod
    def _partner(cls, name):
        return cls.env["res.partner"].create({
            "name": name.replace("_", " ").title(),
            "email": "%s@example.test" % name,
        })

    @classmethod
    def _user(cls, partner, login, share):
        group = cls.portal_group if share else cls.internal_group
        return cls.Users.create({
            "name": partner.name,
            "login": login,
            "partner_id": partner.id,
            "group_ids": [Command.set([group.id])],
        })

    @classmethod
    def _staff(cls, partner, role):
        return cls.env["sports.team.staff"].create({
            "team_id": cls.team.id,
            "partner_id": partner.id,
            "role": role,
        })

    def _portal_url(self):
        return "%s/my/team?team_id=%s" % (self.BASE_URL, self.team.id)

    def _backend_url(self):
        return "%s/odoo/action-%s/%s" % (
            self.BASE_URL, self.action.id, self.team.id
        )

    def _urgent_recipients(self):
        """Run the urgent recipient builder over one synthetic status change
        on the shared team and return ``{partner_id: [summary, ...]}``."""
        return self.Patient._urgent_notify_build_recipients(
            {self.team.id: {self.patient.id: set()}}, {}, {}
        )

    def _urgent_url_for(self, partner):
        summaries = self._urgent_recipients().get(partner.id)
        self.assertTrue(
            summaries, "%s should be an urgent recipient" % partner.name
        )
        self.assertEqual(len(summaries), 1)
        return summaries[0]["url"]

    def _briefing_url_for(self, user):
        cutoff = self.Patient._dashboard_window_cutoff()
        lines, _events = user._digest_build_for_user(
            fields.Datetime.now(), cutoff, self.BASE_URL
        )
        for line in lines:
            if line["id"] == self.team.id:
                return line["url"]
        self.fail("no briefing line for team on user %s" % user.login)

    # ------------------------------------------------------- shared formatter
    def test_formatter_portal_is_the_default(self):
        self.assertEqual(
            self.team._dashboard_url(self.BASE_URL), self._portal_url()
        )
        self.assertEqual(
            self.team._dashboard_url(self.BASE_URL, internal=False),
            self._portal_url(),
        )

    def test_formatter_internal_is_the_backend_action(self):
        self.assertEqual(
            self.team._dashboard_url(self.BASE_URL, internal=True),
            self._backend_url(),
        )

    def test_formatter_keeps_empty_base_url_guard(self):
        """The portal branch keeps its pre-existing ``if base_url else ''``."""
        self.assertEqual(self.team._dashboard_url(""), "")

    # ----------------------------------------------------------------- urgent
    def test_urgent_portal_coach_gets_portal_link(self):
        self.assertEqual(
            self._urgent_url_for(self.p_portal), self._portal_url()
        )

    def test_urgent_internal_staff_gets_backend_link(self):
        self.assertEqual(
            self._urgent_url_for(self.p_internal), self._backend_url()
        )

    def test_urgent_contact_without_user_gets_portal_link(self):
        self.assertEqual(
            self._urgent_url_for(self.p_contact), self._portal_url()
        )

    def test_urgent_partner_with_both_user_kinds_gets_backend_link(self):
        self.assertEqual(
            self._urgent_url_for(self.p_both), self._backend_url()
        )

    def test_urgent_archived_internal_with_active_portal_gets_portal_link(self):
        """Their internal access was revoked, so the backend link is dead — the
        active portal login is what they can actually open."""
        self.assertEqual(
            self._urgent_url_for(self.p_revoked_internal), self._portal_url()
        )

    def test_urgent_mixed_recipients_same_team_same_run(self):
        """One run, one team, recipients of different types -> different links."""
        recipients = self._urgent_recipients()
        self.assertEqual(
            recipients[self.p_portal.id][0]["url"], self._portal_url()
        )
        self.assertEqual(
            recipients[self.p_internal.id][0]["url"], self._backend_url()
        )
        self.assertEqual(
            recipients[self.p_contact.id][0]["url"], self._portal_url()
        )
        self.assertEqual(
            recipients[self.p_both.id][0]["url"], self._backend_url()
        )

    def test_urgent_rendered_mail_carries_the_recipient_link(self):
        """End-to-end through the cron: the delivered body of each recipient
        carries THEIR link, not the other one."""
        self.patient.write({"match_status": "no", "practice_status": "no"})
        self.env.cr.precommit.run()
        self.Patient._urgent_notify_set_watermark(
            fields.Datetime.now() - timedelta(hours=1)
        )
        self.Patient._cron_send_urgent_notifications(
            now=fields.Datetime.now() + timedelta(hours=1)
        )
        msgs = self.env["mail.message"].search([
            ("subject", "=like", "FitCrew — urgent%"),
        ])
        self.assertTrue(msgs)

        def _body_for(partner):
            notifs = self.env["mail.notification"].search([
                ("mail_message_id", "in", msgs.ids),
                ("res_partner_id", "=", partner.id),
            ])
            self.assertTrue(notifs, "no urgent mail for %s" % partner.name)
            return " ".join(notifs.mail_message_id.mapped("body"))

        portal_body = _body_for(self.p_portal)
        self.assertIn("/my/team?team_id=%s" % self.team.id, portal_body)
        self.assertNotIn("/odoo/action-", portal_body)

        internal_body = _body_for(self.p_internal)
        self.assertIn(
            "/odoo/action-%s/%s" % (self.action.id, self.team.id), internal_body
        )
        self.assertNotIn("/my/team?team_id=", internal_body)

    # --------------------------------------------------------------- briefing
    def test_briefing_internal_staff_gets_backend_link(self):
        """The mirror fix: internal staff used to get the portal link."""
        self.assertEqual(
            self._briefing_url_for(self.u_internal), self._backend_url()
        )

    def test_briefing_portal_coach_still_gets_portal_link(self):
        self.assertEqual(
            self._briefing_url_for(self.u_portal), self._portal_url()
        )

    def test_briefing_uses_share_not_partner_inference(self):
        """``self.share`` is the exact per-recipient signal on this surface: the
        partner with BOTH an active portal and an active internal user gets the
        backend link on the internal login and the portal link on the portal
        login — a partner-side inference could not tell them apart."""
        both_portal = self.Users.search([("login", "=", "both_portal")])
        both_internal = self.Users.search([("login", "=", "both_internal")])
        self.assertEqual(
            self._briefing_url_for(both_portal), self._portal_url()
        )
        self.assertEqual(
            self._briefing_url_for(both_internal), self._backend_url()
        )

    def test_briefing_keeps_empty_base_url_guard(self):
        cutoff = self.Patient._dashboard_window_cutoff()
        lines, _events = self.u_portal._digest_build_for_user(
            fields.Datetime.now(), cutoff, ""
        )
        self.assertTrue(lines)
        self.assertEqual(lines[0]["url"], "")

    # ------------------------------------------------------------- regression
    def test_archived_users_still_receive_nothing(self):
        """Unchanged eligibility: a contact whose only user is archived is not
        an urgent recipient and not a briefing recipient. This is why the link
        decision must NOT be folded into ``_is_follower_eligible``."""
        staff = self.env["sports.team.staff"].search([
            ("team_id", "=", self.team.id),
            ("partner_id", "=", self.p_archived_only.id),
        ])
        self.assertFalse(staff._is_follower_eligible())
        self.assertNotIn(self.p_archived_only.id, self._urgent_recipients())
        self.assertNotIn(
            self.u_archived_only, self.Users._digest_eligible_users()
        )

    def test_revoked_internal_user_is_not_a_briefing_recipient(self):
        """The archived internal login itself gets no briefing; only the still
        active portal login of the same person does."""
        eligible = self.Users._digest_eligible_users()
        self.assertNotIn(self.u_revoked_internal, eligible)
        self.assertIn(self.u_revoked_portal, eligible)
