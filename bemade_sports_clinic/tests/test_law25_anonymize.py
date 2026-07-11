"""Law 25 retention-anonymization tests (bemade_sports_clinic).

Acceptance criteria exercised here:
  * Manual-mode rule: the recycle cron only *creates* review candidates; NO PII
    is changed until an admin validates (owner-review gate).
  * On validate, a >5y-since-last-consultation player with no active team has
    identity PII irreversibly overwritten on BOTH sports.patient AND res.partner,
    is_anonymized=True, and an audit note is logged.
  * A within-5y player, a still-rostered player and a plain (non-player) partner
    are untouched.
  * Re-running is idempotent (already-anonymized excluded / no-op).
  * Retention delay is configurable on the rule; default = 5 years on
    last_consultation_date.
  * Legally-retained data (an invoice on the partner) survives anonymization.
  * No residual PII in the anonymized record's OWN chatter/tracking: no
    mail.tracking.value and no mail.message on either record restates the old
    identity (incl. the anonymizing write not logging the old value).
"""

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "law25")
class TestLaw25Anonymize(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.rule = cls.env.ref(
            "bemade_sports_clinic.data_recycle_model_law25_patient"
        )
        cls.today = fields.Date.today()
        cls.team = cls.env["sports.team"].create({"name": "Retention FC"})

    def _make_player(self, first, last, last_consult, team=False, **extra):
        vals = {
            "first_name": first,
            "last_name": last,
            "last_consultation_date": last_consult,
        }
        if team:
            vals["team_ids"] = [(6, 0, team.ids)]
        vals.update(extra)
        return self.env["sports.patient"].create(vals)

    def _run_scan(self):
        """Run the recycle scan (candidate creation only, no validation)."""
        self.rule._recycle_records()

    def _candidate_for(self, patient):
        return self.env["data_recycle.record"].search(
            [
                ("recycle_model_id", "=", self.rule.id),
                ("res_id", "=", patient.id),
            ]
        )

    # ------------------------------------------------------------------ rule
    def test_rule_defaults(self):
        """Default rule: manual mode, anonymize action, 5 years on
        last_consultation_date, and is-anonymized/no-team domain."""
        self.assertEqual(self.rule.recycle_mode, "manual")
        self.assertEqual(self.rule.recycle_action, "anonymize")
        self.assertEqual(self.rule.time_field_id.name, "last_consultation_date")
        self.assertEqual(self.rule.time_field_delta, 5)
        self.assertEqual(self.rule.time_field_delta_unit, "years")

    # ------------------------------------------------------ manual review gate
    def test_manual_gate_creates_candidate_without_touching_pii(self):
        player = self._make_player(
            "Gordie", "Howe", self.today - relativedelta(years=6)
        )
        self._run_scan()
        candidate = self._candidate_for(player)
        self.assertTrue(candidate, "A review candidate should be created")
        # Nothing anonymized until an admin validates.
        self.assertFalse(player.is_anonymized)
        self.assertEqual(player.first_name, "Gordie")
        self.assertEqual(player.partner_id.name, "Gordie Howe")

    # -------------------------------------------------------- full anonymize
    def test_validate_anonymizes_both_models(self):
        player = self._make_player(
            "Maurice",
            "Richard",
            self.today - relativedelta(years=7),
            email="rocket@example.com",
            phone="+1 514 555 0101",
            date_of_birth=self.today - relativedelta(years=40),
            team_info_notes="Confidential note",
            return_date=self.today - relativedelta(years=6),
        )
        partner = player.partner_id
        old_name, old_email, old_phone = "Maurice Richard", "rocket@example.com", "+1 514 555 0101"
        # street lives on the partner (patient.street is related)
        partner.write({"street": "123 Forum St", "city": "Montreal"})

        self._run_scan()
        candidate = self._candidate_for(player)
        self.assertTrue(candidate)

        candidate.action_validate()

        # Identity PII wiped on the patient
        self.assertTrue(player.is_anonymized)
        self.assertNotIn("Maurice", player.first_name)
        self.assertNotIn("Richard", player.last_name)
        self.assertFalse(player.date_of_birth)
        self.assertFalse(player.team_info_notes)
        self.assertFalse(player.return_date)
        # ... and on the partner
        self.assertNotIn("Maurice", partner.name)
        self.assertFalse(partner.email)
        self.assertFalse(partner.phone)
        self.assertFalse(partner.street)
        self.assertFalse(partner.city)
        # related fields on the patient reflect the cleared partner
        self.assertFalse(player.email)
        self.assertFalse(player.phone)

        # Audit note present, restating no old PII
        messages = self.env["mail.message"].search(
            [("model", "=", "sports.patient"), ("res_id", "=", player.id)]
        )
        self.assertTrue(messages, "An audit note should be logged")
        for msg in messages:
            body = (msg.body or "") + (msg.subject or "")
            self.assertNotIn(old_name, body)
            self.assertNotIn(old_email, body)
            self.assertNotIn(old_phone, body)

        # No residual PII in chatter/tracking on EITHER record
        self._assert_no_residual_pii(player, [old_name, old_email, old_phone, "Maurice", "Richard"])
        self._assert_no_residual_pii(partner, [old_name, old_email, old_phone, "Maurice", "Richard"])

    def _assert_no_residual_pii(self, record, needles):
        messages = self.env["mail.message"].search(
            [("model", "=", record._name), ("res_id", "=", record.id)]
        )
        tracking = self.env["mail.tracking.value"].search(
            [("mail_message_id", "in", messages.ids)]
        )
        self.assertFalse(
            tracking, "No tracking values should remain on an anonymized record"
        )
        for msg in messages:
            haystack = " ".join(
                filter(None, [msg.body, msg.subject, msg.email_from])
            )
            for needle in needles:
                self.assertNotIn(
                    needle, haystack, "PII %r leaked in chatter" % needle
                )

    # ----------------------------------------------------------- exclusions
    def test_within_retention_not_surfaced(self):
        player = self._make_player(
            "Recent", "Player", self.today - relativedelta(years=2)
        )
        self._run_scan()
        self.assertFalse(self._candidate_for(player))

    def test_rostered_player_not_surfaced(self):
        player = self._make_player(
            "Active", "Roster", self.today - relativedelta(years=8), team=self.team
        )
        self._run_scan()
        self.assertFalse(self._candidate_for(player))

    def test_plain_partner_untouched(self):
        partner = self.env["res.partner"].create(
            {"name": "Just A Contact", "email": "contact@example.com"}
        )
        self._run_scan()
        # The rule targets sports.patient only.
        self.assertEqual(partner.name, "Just A Contact")
        self.assertEqual(partner.email, "contact@example.com")

    # ----------------------------------------------------------- idempotency
    def test_idempotent_rerun(self):
        player = self._make_player(
            "Jean", "Beliveau", self.today - relativedelta(years=9)
        )
        self._run_scan()
        self._candidate_for(player).action_validate()
        self.assertTrue(player.is_anonymized)
        anon_name = player.partner_id.name

        # A second scan must not surface the already-anonymized player.
        self._run_scan()
        self.assertFalse(self._candidate_for(player))
        # A direct re-anonymize is a no-op guard.
        player._law25_anonymize()
        self.assertEqual(player.partner_id.name, anon_name)

    # --------------------------------------------------- legal-retention data
    def test_invoice_survives_anonymization(self):
        player = self._make_player(
            "Guy", "Lafleur", self.today - relativedelta(years=6)
        )
        partner = player.partner_id
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "invoice_line_ids": [
                    (0, 0, {"name": "Physio session", "quantity": 1, "price_unit": 100.0})
                ],
            }
        )
        self._run_scan()
        self._candidate_for(player).action_validate()

        self.assertTrue(invoice.exists())
        self.assertEqual(invoice.partner_id, partner)
        self.assertEqual(invoice.amount_total, 100.0)

    # --------------------------------------------------------- configurable
    def test_delta_is_configurable(self):
        """Tightening the rule to 3 years surfaces a 4-year-old player that the
        5-year default would exclude."""
        player = self._make_player(
            "Config", "Urable", self.today - relativedelta(years=4)
        )
        self._run_scan()
        self.assertFalse(self._candidate_for(player))
        self.rule.time_field_delta = 3
        self._run_scan()
        self.assertTrue(self._candidate_for(player))
