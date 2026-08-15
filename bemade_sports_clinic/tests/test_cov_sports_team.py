from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import Form, TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestCovSportsTeam(TransactionCase):
    """Coverage for sports.team and sports.team.staff (computes, roles, group sync)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.org = cls.env['res.partner'].create({'name': 'Team Org', 'is_company': True})
        cls.team = cls.env['sports.team'].create({'name': 'Cov Team', 'parent_id': cls.org.id})

        cls.group_user = cls.env.ref('base.group_user')
        cls.group_portal = cls.env.ref('base.group_portal')
        cls.tp_group = cls.env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        cls.portal_coach_group = cls.env.ref('bemade_sports_clinic.group_portal_team_coach')

        cls.internal_user = cls.env['res.users'].create({
            'name': 'Internal Coach', 'login': 'cov_team_internal', 'email': 'cov_ti@example.com',
            'group_ids': [Command.link(cls.group_user.id)],
        })
        cls.portal_user = cls.env['res.users'].create({
            'name': 'Portal Coach', 'login': 'cov_team_portal', 'email': 'cov_tp@example.com',
            'group_ids': [Command.link(cls.group_portal.id)],
        })

    def _staff(self, role, partner=None, **vals):
        partner = partner or self.env['res.partner'].create({'name': f'Staff {role}'})
        return self.env['sports.team.staff'].create({
            'team_id': self.team.id, 'partner_id': partner.id, 'role': role, **vals,
        })

    # ----- team computes -----

    def test_compute_player_counts(self):
        healthy = self.env['sports.patient'].create({'first_name': 'H', 'last_name': 'P'})
        injured = self.env['sports.patient'].create({
            'first_name': 'I', 'last_name': 'P', 'match_status': 'no', 'practice_status': 'no',
        })
        self.team.patient_ids = [Command.set([healthy.id, injured.id])]
        self.assertEqual(self.team.player_count, 2)
        self.assertEqual(self.team.injured_count, 1)
        self.assertEqual(self.team.healthy_count, 1)

    def test_compute_head_coach_and_therapist(self):
        coach = self._staff('head_coach')
        ther = self._staff('head_therapist')
        self.assertEqual(self.team.head_coach_id, coach.partner_id)
        self.assertEqual(self.team.head_therapist_id, ther.partner_id)

    def test_compute_activity_count(self):
        self.env['mail.activity'].create({
            'res_model_id': self.env['ir.model']._get('sports.team').id,
            'res_id': self.team.id,
            'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
            'summary': 'x',
        })
        self.team.invalidate_recordset(['activity_count'])
        self.assertEqual(self.team.activity_count, 1)

    # ----- staff roles + constraints -----

    @mute_logger('odoo.addons.bemade_sports_clinic.models.sports_team')
    def test_constrain_single_head_coach(self):
        self._staff('head_coach')
        with self.assertRaises(ValidationError):
            self._staff('head_coach')

    def test_has_role_helpers(self):
        self.assertTrue(self._staff('therapist')._has_therapist_role())
        self.assertTrue(self._staff('head_therapist')._has_therapist_role())
        self.assertTrue(self._staff('coach')._has_coach_role())
        self.assertFalse(self._staff('other')._has_therapist_role())

    def test_get_staff_with_roles(self):
        partner = self.env['res.partner'].create({'name': 'Role Partner'})
        staff = self._staff('therapist', partner=partner)
        found = staff._get_staff_with_therapist_roles(partner.id)
        self.assertIn(staff, found)
        self.assertFalse(staff._get_staff_with_coach_roles(partner.id))

    def test_group_getters(self):
        staff = self._staff('therapist')
        self.assertEqual(staff._get_treatment_professional_group(), self.tp_group)
        self.assertEqual(staff._get_portal_coach_group(), self.portal_coach_group)

    # ----- allowed_user_ids inverse + remove_access -----

    def test_inverse_allowed_user_ids_creates_and_removes_staff(self):
        self.team.allowed_user_ids = [Command.set([self.internal_user.id])]
        self.assertIn(self.internal_user, self.team.staff_ids.user_ids)
        # Removing the user from allowed_user_ids should unlink the staff record.
        self.team.allowed_user_ids = [Command.clear()]
        self.assertNotIn(self.internal_user, self.team.staff_ids.user_ids)

    def test_remove_access_unlinks_staff(self):
        staff = self._staff('therapist', partner=self.internal_user.partner_id)
        self.team.remove_access(self.internal_user)
        self.assertFalse(staff.exists())

    def test_write_accepts_vals_keyword(self):
        """Regression (task 1378): sports.team.staff.write() must accept the
        standard Odoo ``vals`` keyword so external RPC / update_records writes
        (which call write(vals=...) by keyword) succeed. Before the param
        rename this raised: write() got an unexpected keyword argument 'vals'."""
        staff = self._staff('coach', silent_notifications=False)
        staff.write(vals={'silent_notifications': True})
        self.assertTrue(staff.silent_notifications)

    # ----- portal access compute + group sync -----

    def test_compute_has_portal_access(self):
        staff = self._staff('coach', partner=self.portal_user.partner_id)
        self.assertTrue(staff.has_portal_access)

    def test_create_staff_grants_internal_treatment_group(self):
        self._staff('therapist', partner=self.internal_user.partner_id)
        self.assertIn(self.tp_group, self.internal_user.group_ids,
                      "internal therapist staff should gain the treatment professional group")

    def test_create_staff_grants_portal_coach_group(self):
        self._staff('coach', partner=self.portal_user.partner_id)
        self.assertIn(self.portal_coach_group, self.portal_user.group_ids,
                      "portal coach staff should gain the portal coach group")

    def test_update_all_portal_groups_manual(self):
        self._staff('therapist', partner=self.internal_user.partner_id)
        self.assertTrue(self.env['sports.team.staff'].update_all_portal_groups())
        self.assertTrue(self.env['sports.team.staff'].update_all_treatment_professional_groups())

    def test_update_treatment_professional_group_specific_user(self):
        staff = self._staff('therapist', partner=self.internal_user.partner_id)
        staff._update_treatment_professional_group(specific_user=self.internal_user)
        self.assertIn(self.tp_group, self.internal_user.group_ids)

    # ----- staff phone auto-format (task 1345) -----

    def test_staff_phone_onchange_company_country_fallback(self):
        """Adding a staff line via the team Form auto-formats a local mobile to
        INTERNATIONAL even when the new partner has NO country_id, falling back
        to the company country (regression for task 1345)."""
        self.env.company.country_id = self.env.ref('base.ca')
        # A brand-new staff partner with no country set.
        partner = self.env['res.partner'].create({
            'name': 'No-Country Coach', 'is_company': False,
        })
        self.assertFalse(partner.country_id)
        with Form(self.env['sports.team']) as team_form:
            team_form.name = 'Phone Fmt Team'
            with team_form.staff_ids.new() as line:
                line.partner_id = partner
                line.role = 'coach'
                line.mobile = '5145551234'
                # The onchange fires inside the Form; mobile is reformatted.
                formatted = line.mobile
        self.assertTrue(formatted.startswith('+1'),
                        "local number should auto-format to INTERNATIONAL via "
                        "the company-country fallback, got %r" % formatted)
        self.assertIn('514', formatted)

    def test_staff_phone_format_partner_country(self):
        """The partner-has-country path also formats to INTERNATIONAL."""
        ca = self.env.ref('base.ca')
        partner = self.env['res.partner'].create({
            'name': 'CA Coach', 'is_company': False, 'country_id': ca.id,
        })
        staff = self._staff('coach', partner=partner)
        formatted = staff._phone_format('5145551234', force_format='INTERNATIONAL')
        self.assertTrue(formatted.startswith('+1'))
        self.assertIn('514', formatted)

    @mute_logger('odoo.addons.phone_validation.tools.phone_validation')
    def test_staff_phone_format_invalid_passthrough(self):
        """An unparseable number passes through untouched, no exception."""
        ca = self.env.ref('base.ca')
        partner = self.env['res.partner'].create({
            'name': 'Bad Number Coach', 'is_company': False, 'country_id': ca.id,
        })
        staff = self._staff('doctor', partner=partner)
        self.assertEqual(
            staff._phone_format('not-a-number', force_format='INTERNATIONAL'),
            'not-a-number',
        )
