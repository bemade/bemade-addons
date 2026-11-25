"""Task 1674 — « Possible duplicates »: a clinic-admin review list of player
pairs the shared name matcher (models/sc_name_match.py) finds likely to be
the same person. Computed on demand (« Find duplicates »), never on every
write; each pair opens the existing Merge Players wizard, or is dismissed
for good (« Not a duplicate »). Nothing is ever merged automatically."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .sc_name_match import compact, duplicate_pairs


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
    ], string='Kind', required=True)
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

    @api.model
    def _sc_match_row(self, row):
        """Task 1715: the name the matcher compares is the one users see —
        the player's display name (its contact's name). When the first /
        last name fields agree with it (normalised: accents, case, spaces,
        hyphens), they are used as they are (first vs last, so « swapped »
        and the near checks keep working). When they disagree (a
        half-overwritten record), the display name is split first word /
        rest and the row is untrusted: never « Same name » / « swapped »,
        at most « Similar name ». -> ``(id, first, last, dob, trusted)``."""
        first, last = row['first_name'] or '', row['last_name'] or ''
        display = (row.get('name') or '').strip()
        if not display or compact('%s %s' % (first, last)) == compact(display):
            return (row['id'], first, last, row['date_of_birth'], True)
        head, _sep, rest = display.partition(' ')
        return (row['id'], head, rest.strip(), row['date_of_birth'], False)

    def action_find_duplicates(self):
        # Review 2026-10-25: no @api.model: the list-header button calls it with
        # the (empty) selection, which @api.model rejected as an extra argument.
        """Recompute the open pairs (dismissed ones stay dismissed) and show
        the list."""
        patients = self.env['sports.patient'].search_read(
            [], ['first_name', 'last_name', 'date_of_birth', 'name'])
        found = duplicate_pairs([self._sc_match_row(row) for row in patients])
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
