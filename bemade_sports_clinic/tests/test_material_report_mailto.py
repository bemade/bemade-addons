import urllib.parse
from datetime import datetime

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMaterialReportMailto(TransactionCase):
    """Server-side coverage for sports.event._get_material_report_mailto().

    The portal modal + the actual mailto click/href + French RENDERING are
    browser behaviour and are NOT covered here (UAT at /dev-review). What is
    pinned: the config param is read, the recipient is switchable via Settings,
    the subject references the event, and it is properly URL-encoded.
    All fixtures are SYNTHETIC (bemade-addons is public).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Activate fr_CA so the French msgstr for the subject is loaded from the
        # module's .po (this also imports our new i18n entry).
        cls.env['res.lang']._activate_lang('fr_CA')
        cls.org = cls.env['res.partner'].create({'name': 'MR Org', 'is_company': True})
        cls.team = cls.env['sports.team'].create({'name': 'MR Team', 'parent_id': cls.org.id})
        cls.ICP = cls.env['ir.config_parameter'].sudo()

    def _event(self, **vals):
        vals.setdefault('name', 'MR Event')
        vals.setdefault('team_ids', [Command.set([self.team.id])])
        vals.setdefault('date_start', datetime(2026, 3, 4, 14, 0))
        vals.setdefault('date_end', datetime(2026, 3, 4, 16, 0))
        vals.setdefault('state', 'confirmed')
        return self.env['sports.event'].create(vals)

    def test_default_recipient_and_scheme(self):
        """With the seeded default, the mailto targets admin@lefitcrew.com."""
        self.ICP.set_param('bemade_sports_clinic.material_report_email', 'admin@lefitcrew.com')
        ev = self._event()
        mailto = ev._get_material_report_mailto()
        self.assertTrue(mailto.startswith('mailto:'))
        # '@' is percent-encoded (%40) by urllib.parse.quote.
        self.assertIn('admin%40lefitcrew.com', mailto)
        self.assertIn('?subject=', mailto)

    def test_recipient_follows_config_param(self):
        """Changing the Setting changes the mailto recipient (config wired)."""
        self.ICP.set_param('bemade_sports_clinic.material_report_email', 'billing@example.com')
        ev = self._event()
        mailto = ev._get_material_report_mailto()
        self.assertIn('mailto:billing%40example.com', mailto)
        self.assertNotIn('admin%40lefitcrew.com', mailto)

    def test_fallback_when_param_missing(self):
        """Belt-and-suspenders: empty/unset param falls back to the default."""
        self.ICP.set_param('bemade_sports_clinic.material_report_email', '')
        ev = self._event()
        mailto = ev._get_material_report_mailto()
        self.assertIn('admin%40lefitcrew.com', mailto)

    def test_subject_references_event_and_is_encoded(self):
        """Subject names THIS event; accents/spaces/& are URL-encoded, not raw."""
        self.ICP.set_param('bemade_sports_clinic.material_report_email', 'admin@lefitcrew.com')
        ev = self._event(name='Tournoi Été & Café')
        mailto = ev._get_material_report_mailto()
        # No raw space, accent, or ampersand leaks into the URL.
        self.assertNotIn(' ', mailto)
        self.assertNotIn('Été', mailto)
        self.assertNotIn('&', mailto.split('?', 1)[1].replace('&subject', ''))  # no stray unencoded &
        # Decoding the subject recovers the event name.
        subject = urllib.parse.parse_qs(mailto.split('?', 1)[1])['subject'][0]
        self.assertIn('Tournoi Été & Café', subject)

    def test_subject_renders_french_for_fr_ca(self):
        """In an fr_CA context the subject uses the French msgstr."""
        self.ICP.set_param('bemade_sports_clinic.material_report_email', 'admin@lefitcrew.com')
        ev = self._event(name='Match test')
        mailto = ev.with_context(lang='fr_CA')._get_material_report_mailto()
        subject = urllib.parse.parse_qs(mailto.split('?', 1)[1])['subject'][0]
        self.assertIn('Matériel personnel utilisé', subject)
