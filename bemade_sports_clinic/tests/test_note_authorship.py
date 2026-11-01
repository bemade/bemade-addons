"""Treatment notes: authorship shows the author's full name and the date
with the time (owner review 2026-10-11; was initials and the date only),
and still says whether the note is « General » or about an injury.
Synthetic fixtures only.

Acceptance criteria:

* UC-NA1 A note written on its own date reads « <date> <time> » (the time it
  was written, in the viewer's time zone); a note dated another day (e.g.
  backdated) reads its date only — never a misleading time.
* UC-NA2 The app shell note card shows the author's full name and that
  date/time, and « General » or the injury's name, as before.
* UC-NA3 The « modified on … by … » caption gives the date with the time and
  the editor's full name.
"""
import re
from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_player_inline import PlayerInlineCommon

TIME = re.compile(r'\d{1,2}[:h]\d{2}')


@tagged('post_install', '-at_install')
class TestNoteAuthorship(PlayerInlineCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Portal therapists add notes through the controllers (sudo).
        Note = cls.env['sports.treatment.note'].sudo()
        cls.general = Note.create({'patient_id': cls.player.id, 'note': 'Synthetic general',
                                   'user_id': cls.tp.id})
        cls.specific = Note.create({'patient_id': cls.player.id, 'injury_id': cls.injury.id,
                                    'note': 'Synthetic specific', 'user_id': cls.tp.id})

    # -- UC-NA1 ----------------------------------------------------------
    def test_when_label(self):
        self.assertRegex(self.general.portal_when_label, TIME)
        self.general.sudo().write({'date': fields.Date.today() - timedelta(days=5)})
        self.general.invalidate_recordset()
        self.assertNotRegex(self.general.portal_when_label, TIME)
        self.assertTrue(self.general.portal_when_label)

    # -- UC-NA2 ----------------------------------------------------------
    def test_note_card(self):
        self._switch(True)
        self._login_tp()
        _text, tree = self._get(self._url(tab='notes'))
        cards = {int(c.get('data-sc-note-id')): ' '.join(c.text_content().split())
                 for c in tree.xpath('//*[contains(@class, "o_sc_note_card")]')}
        for note in (self.general, self.specific):
            self.assertIn(self.tp.name, cards[note.id])
            self.assertRegex(cards[note.id], TIME)
        self.assertIn('General', cards[self.general.id])
        self.assertIn(self.injury.diagnosis, cards[self.specific.id])

    # -- UC-NA3 ----------------------------------------------------------
    def test_modified_label(self):
        self.general.sudo().with_user(self.tp).sudo().write({'note': 'Synthetic general — revised'})
        self.env.cr.execute("UPDATE sports_treatment_note SET write_uid=%s WHERE id=%s",
                            (self.tp.id, self.general.id))
        self.env.cr.execute("UPDATE sports_treatment_note SET create_date=%s WHERE id=%s",
                            (fields.Datetime.now() - timedelta(hours=2), self.general.id))
        self.general.invalidate_recordset()
        label = self.general.modified_label
        self.assertIn(self.tp.name, label)
        self.assertRegex(label, TIME)
