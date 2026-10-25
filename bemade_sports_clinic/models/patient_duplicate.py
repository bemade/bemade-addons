"""Task 1674 — « Possible duplicates »: a clinic-admin review list of player
pairs the shared name matcher (models/sc_name_match.py) finds likely to be
the same person. Computed on demand (« Find duplicates »), never on every
write; each pair opens the existing Merge Players wizard, or is dismissed
for good (« Not a duplicate »). Nothing is ever merged automatically."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .sc_name_match import duplicate_pairs


class SportsPatientDuplicate(models.Model):
    _name = 'sports.patient.duplicate'
    _description = 'Possible duplicate players'
    _order = 'same_dob desc, kind_sequence, id'

    patient_a_id = fields.Many2one('sports.patient', string='Player', required=True, ondelete='cascade',
                                   index=True)
    patient_b_id = fields.Many2one('sports.patient', string='Possible duplicate', required=True,
                                   ondelete='cascade', index=True)
    kind = fields.Selection([
        ('exact', 'Same name'),
        ('swapped', 'First and last name swapped'),
        ('near', 'Similar name'),
    ], required=True)
    kind_sequence = fields.Integer(compute='_compute_kind_sequence', store=True)
    same_dob = fields.Boolean(string='Same date of birth')
    dob_a = fields.Date(related='patient_a_id.date_of_birth', string='Date of birth')
    dob_b = fields.Date(related='patient_b_id.date_of_birth', string='Date of birth (duplicate)')
    teams_a = fields.Char(compute='_compute_teams', string='Teams')
    teams_b = fields.Char(compute='_compute_teams', string='Teams (duplicate)')
    dismissed = fields.Boolean(string='Not a duplicate', index=True)

    _pair_unique = models.Constraint('UNIQUE(patient_a_id, patient_b_id)', 'This pair is already listed.')

    @api.depends('kind')
    def _compute_kind_sequence(self):
        order = {'exact': 0, 'swapped': 1, 'near': 2}
        for pair in self:
            pair.kind_sequence = order.get(pair.kind, 9)

    def _compute_teams(self):
        for pair in self:
            pair.teams_a = ', '.join(pair.patient_a_id.team_ids.mapped('name'))
            pair.teams_b = ', '.join(pair.patient_b_id.team_ids.mapped('name'))

    def action_find_duplicates(self):
        # Review 2026-10-25: no @api.model: the list-header button calls it with
        # the (empty) selection, which @api.model rejected as an extra argument.
        """Recompute the open pairs (dismissed ones stay dismissed) and show
        the list."""
        patients = self.env['sports.patient'].search_read(
            [], ['first_name', 'last_name', 'date_of_birth'])
        found = duplicate_pairs([
            (row['id'], row['first_name'] or '', row['last_name'] or '', row['date_of_birth'])
            for row in patients])
        existing = self.with_context(active_test=False).search([])
        dismissed = {(p.patient_a_id.id, p.patient_b_id.id) for p in existing if p.dismissed}
        existing.filtered(lambda p: not p.dismissed).unlink()
        self.create([
            {'patient_a_id': a, 'patient_b_id': b, 'kind': kind, 'same_dob': same_dob}
            for a, b, kind, same_dob in found if (a, b) not in dismissed])
        return self.env['ir.actions.act_window']._for_xml_id(
            'bemade_sports_clinic.action_sports_patient_duplicate')

    def action_merge(self):
        """The existing Merge Players wizard, the pair preselected."""
        self.ensure_one()
        patients = self.patient_a_id | self.patient_b_id
        if len(patients.exists()) < 2:
            raise UserError(_("One of these players no longer exists."))
        action = self.env['ir.actions.act_window']._for_xml_id('bemade_sports_clinic.action_sports_patient_merge')
        action['context'] = {'active_model': 'sports.patient', 'active_ids': patients.ids}
        return action

    def action_dismiss(self):
        self.write({'dismissed': True})
        return True
