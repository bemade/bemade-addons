"""Merge Players wizard: suggesting other contacts to fold into the same merge.

Motivation from the prod incident: the player had THREE contacts but only two
patients. The third (no patient attached) was a duplicate too. Consolidating the patients alone would have left it behind, and staff would
have been straight back to the contact-merge workaround that caused the damage.

Policy agreed with the owner (2026-07-15, revised after the restored backup was
examined): suggest on exact email OR sanitised phone OR same last name -- a match
on ANY of those surfaces the contact for optional inclusion. Suggestions are
always user-selected, never auto-included.

The revision is evidence-driven. In the real incident the two patient partners
carried '514-555-0142' and '+1 514-555-0142' (same number, different formatting,
which sanitise identically), and the third duplicate contact had NO phone and
NO email at all. Exact email/phone matching would have found
nothing and suggested nothing -- leaving staff exactly where they started.

ACCEPTANCE CRITERIA
-------------------
AC1  Given the merged patients' partners, the wizard suggests other res.partner
     records matching on ANY of: exact email, sanitised phone, or same last name.
AC1b The last-name rule is what catches a duplicate contact carrying no email and
     no phone -- the case the real incident left behind. Because it is the
     noisiest rule (common surnames: Tremblay, Gagnon), matches must be presented
     with enough context to judge (name, email, phone, linked player if any) and
     must never be pre-ticked.
AC2  Suggestions EXCLUDE partners already part of the merge (the destination's
     and the sources' own partners must not be offered back).
AC3  A partner attached to a DIFFERENT patient is never suggested as a contact to
     fold in. Doing so would smuggle a patient into the res.partner merge behind
     the guard's back and re-create the original deletion bug.
AC3b The user is nonetheless ADVISED when this case arises: such a partner is
     reported in the wizard as an unmergeable match, naming the player it belongs
     to, so staff can reconcile (merge those players, or correct the duplicate
     email/phone) before re-attempting. Silently omitting it would leave staff
     believing the duplicate was handled, which is how the original workaround
     started. The advisory must not offer it as a tickable suggestion.
AC4  Suggestions are opt-in: running the wizard without ticking any leaves every
     suggested partner untouched and unmerged.
AC5  Ticked suggestions are merged into the destination's partner in the same
     transaction as the patient merge.
AC6  Phone matching compares sanitised values -- '514-555-0142' and
     '+1 514-555-0142' are the same phone.
AC7  Empty/false email and phone never match. Two contacts both lacking an email
     must NOT be suggested for each other -- with false == false matching, a
     single merge could sweep in hundreds of unrelated contacts.
AC8  Archived partners are not suggested.
AC9  Suggestion computation is bounded: it must not scan the whole partner table
     per patient in a way that degrades on a 10k-contact database.
"""

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPatientMergeSuggestions(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.sudo().group_ids = [
            Command.link(cls.env.ref(
                'bemade_sports_clinic.group_sports_clinic_treatment_professional').id),
            Command.link(cls.env.ref(
                'bemade_sports_clinic.group_sports_clinic_admin').id),
        ]

    def _patient(self, first_name, last_name='Sampleton', **vals):
        patient = self.env['sports.patient'].create(
            dict(vals, first_name=first_name, last_name=last_name))
        return patient

    def _wizard(self, patients, dst=None):
        Wizard = self.env['sports.patient.merge.wizard'].with_context(
            active_ids=patients.ids)
        values = Wizard.default_get(list(Wizard._fields))
        values['dst_patient_id'] = (dst or patients[0]).id
        return Wizard.create(values)

    def _suggested(self, wizard):
        return wizard.contact_line_ids.filtered(
            lambda l: not l.blocked_patient_id).partner_id

    def test_suggests_partner_sharing_email(self):
        """AC1."""
        dst = self._patient('Alexandre', 'Alpha')
        src = self._patient('Alex', 'Beta')
        dst.partner_id.email = 'shared@example.com'
        dup = self.env['res.partner'].create({
            'name': 'Unrelated Name', 'email': 'shared@example.com'})

        wizard = self._wizard(dst | src, dst)

        self.assertIn(dup, self._suggested(wizard),
                      "a contact sharing an email must be suggested")

    def test_suggests_partner_sharing_phone(self):
        """AC1, AC6: sanitised comparison, the real formatting mismatch."""
        dst = self._patient('Alexandre', 'Alpha')
        src = self._patient('Alex', 'Beta')
        dst.partner_id.phone = '514-555-0142'
        dup = self.env['res.partner'].create({
            'name': 'Unrelated Name', 'phone': '+1 514-555-0142'})
        self.assertEqual(
            dup.phone_sanitized, dst.partner_id.phone_sanitized,
            "fixture precondition: both phones must sanitise identically",
        )

        wizard = self._wizard(dst | src, dst)

        self.assertIn(dup, self._suggested(wizard),
                      "differently-formatted same phone must be suggested")

    def test_suggests_partner_sharing_last_name(self):
        """AC1b: the third-contact case -- no email, no phone, same last name."""
        dst = self._patient('Alexandre')
        src = self._patient('Alex')
        dup = self.env['res.partner'].create({'name': 'Alex Sampleton'})
        self.assertFalse(dup.email or dup.phone,
                         "fixture must have neither email nor phone")

        wizard = self._wizard(dst | src, dst)

        self.assertIn(dup, self._suggested(wizard),
                      "a same-last-name contact with no email/phone must be "
                      "suggested -- this is the contact the real incident left "
                      "behind")

    def test_suggestions_are_not_pre_ticked(self):
        """AC1b."""
        dst = self._patient('Alexandre')
        src = self._patient('Alex')
        self.env['res.partner'].create({'name': 'Alex Sampleton'})

        wizard = self._wizard(dst | src, dst)

        self.assertTrue(wizard.contact_line_ids, "fixture must produce lines")
        self.assertFalse(any(wizard.contact_line_ids.mapped('selected')),
                         "suggestions must never be pre-ticked")

    def test_merge_participants_not_suggested(self):
        """AC2."""
        dst = self._patient('Alexandre')
        src = self._patient('Alex')

        wizard = self._wizard(dst | src, dst)

        suggested = wizard.contact_line_ids.partner_id
        self.assertNotIn(dst.partner_id, suggested,
                         "the destination's own contact must not be offered")
        self.assertNotIn(src.partner_id, suggested,
                         "a source's own contact must not be offered")

    def test_partner_of_another_patient_not_suggested(self):
        """AC3: must not smuggle a patient past the guard."""
        dst = self._patient('Alexandre')
        src = self._patient('Alex')
        other = self._patient('Jonas')  # same last name -> would match

        wizard = self._wizard(dst | src, dst)

        self.assertNotIn(
            other.partner_id, self._suggested(wizard),
            "a contact belonging to another player must never be tickable -- "
            "merging it would delete that player via the core merge",
        )

    def test_partner_of_another_patient_reported_as_unmergeable(self):
        """AC3b: advise the user so they can reconcile first."""
        dst = self._patient('Alexandre')
        src = self._patient('Alex')
        other = self._patient('Jonas')

        wizard = self._wizard(dst | src, dst)

        blocked = wizard.contact_line_ids.filtered('blocked_patient_id')
        self.assertIn(other.partner_id, blocked.partner_id,
                      "the match must be reported, not silently dropped")
        self.assertTrue(wizard.has_blocked_contacts)
        self.assertIn(other.display_name, wizard.blocked_contact_info,
                      "advisory must name the player it belongs to")

    def test_ticking_a_blocked_contact_is_refused(self):
        """AC3: defence in depth.

        The view makes a blocked line's tick box readonly, but if one were
        selected anyway the merge must refuse rather than feed two patients into
        the contact merge -- the exact shape of the original bug.
        """
        dst = self._patient('Alexandre')
        src = self._patient('Alex')
        other = self._patient('Jonas')

        wizard = self._wizard(dst | src, dst)
        blocked = wizard.contact_line_ids.filtered('blocked_patient_id')
        self.assertTrue(blocked, "fixture must produce a blocked line")
        blocked.selected = True

        with self.assertRaises(UserError):
            wizard.action_merge()

        self.assertTrue(other.exists(), "the other player must be untouched")
        self.assertTrue(other.partner_id.exists())
        self.assertTrue(src.exists(), "nothing may be half-merged")

    def test_suggestions_are_opt_in(self):
        """AC4."""
        dst = self._patient('Alexandre')
        src = self._patient('Alex')
        dup = self.env['res.partner'].create({'name': 'Alex Sampleton'})

        self._wizard(dst | src, dst).action_merge()

        self.assertTrue(dup.exists(),
                        "an unticked suggestion must be left alone")

    def test_ticked_suggestion_merged_into_destination_partner(self):
        """AC5."""
        dst = self._patient('Alexandre')
        src = self._patient('Alex')
        dup = self.env['res.partner'].create({'name': 'Alex Sampleton'})

        wizard = self._wizard(dst | src, dst)
        wizard.contact_line_ids.filtered(
            lambda l: l.partner_id == dup).selected = True
        wizard.action_merge()

        self.assertFalse(dup.exists(),
                         "a ticked suggestion must be merged away")
        self.assertTrue(dst.partner_id.exists())

    def test_blank_email_and_phone_never_match(self):
        """AC7: the false==false mass-merge trap."""
        dst = self._patient('Alexandre', 'Alpha')
        src = self._patient('Alex', 'Beta')
        self.assertFalse(dst.partner_id.email or dst.partner_id.phone)
        stranger = self.env['res.partner'].create({'name': 'Totally Unrelated'})

        wizard = self._wizard(dst | src, dst)

        self.assertNotIn(
            stranger, wizard.contact_line_ids.partner_id,
            "a contact with no email/phone and a different last name must not "
            "match -- false == false would sweep in the whole address book",
        )

    def test_archived_partners_not_suggested(self):
        """AC8."""
        dst = self._patient('Alexandre')
        src = self._patient('Alex')
        archived = self.env['res.partner'].create({
            'name': 'Alex Sampleton', 'active': False})

        wizard = self._wizard(dst | src, dst)

        self.assertNotIn(archived, wizard.contact_line_ids.partner_id,
                         "archived contacts must not be suggested")

    def test_suggestion_lookup_is_a_single_search(self):
        """AC9: bounded -- ONE search over res.partner, not one per patient.

        Asserted structurally rather than with a query-count ceiling: a loose
        ceiling passes no matter what, and a tight one breaks on unrelated ORM
        churn. What matters is that every patient's criteria are OR-ed into a
        single domain.
        """
        patients = self.env['sports.patient']
        for index in range(5):
            patients |= self._patient(f'Player{index}', f'Name{index}')
            patients[-1].partner_id.email = f'p{index}@example.com'

        Wizard = self.env['sports.patient.merge.wizard']
        domain = Wizard._match_domain(patients)

        searches = []
        original_search = type(self.env['res.partner']).search

        def counting_search(self_model, args, *a, **kw):
            searches.append(args)
            return original_search(self_model, args, *a, **kw)

        self.patch(type(self.env['res.partner']), 'search', counting_search)
        Wizard._candidate_line_vals(patients)

        self.assertEqual(
            len(searches), 1,
            "candidate lookup must issue exactly one res.partner search "
            f"regardless of patient count, got {len(searches)}",
        )
        # All five emails must ride in that one domain.
        flat = str(domain)
        for index in range(5):
            self.assertIn(f'p{index}@example.com', flat,
                          "every patient's criteria must be OR-ed into the "
                          "single domain, not searched separately")
