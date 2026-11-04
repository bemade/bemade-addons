"""Shared synthetic fixtures for the task 1624 dashboard tests (this
repository is public: invented names only).

Teams (PortalCovCommon + Parity1577Common, plus):

* PC Team A (PC Org): coach, tp, itp, cadmin staff — players « Pat One »
  (healthy), « Red Synth » (red), « Shared Synth » (red, also on Team C);
* PC Team B (PC Org): nobody of ours staffs it — « Pat Two »;
* DB Team C (DB Org Two): tp (therapist) + coach (coach) — « Yellow Synth »
  (yellow), « Shared Synth »;
* AA Unstaffed 1577 (PC Org): « Pat Three ».

Events: today's game (Team A, tp assigned) + a cancelled one; upcoming in 3
days (Team A, tp assigned), in 20 days (Team C, tp assigned), a cancelled
upcoming one; Team B's upcoming practice (nobody of ours).
Announcements: Team A (standing), Team C (expired), Team B (standing).
"""
from datetime import datetime, time, timedelta

from odoo import Command, fields

from odoo.addons.bemade_sports_clinic.tests.test_internal_tp_parity_1577 import Parity1577Common


def _player(env, first, last, teams, match='yes', practice='yes'):
    player = env['sports.patient'].create({'first_name': first, 'last_name': last})
    player.write({'team_ids': [Command.set(teams.ids)],
                  'match_status': match, 'practice_status': practice})
    return player


class Dashboard1624Common(Parity1577Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.env['ir.config_parameter'].sudo().set_param(
            'bemade_sports_clinic.app_shell_enabled', 'True')
        cls.org2 = env['res.partner'].create({'name': 'DB Org Two', 'is_company': True})
        cls.team_c = env['sports.team'].create({'name': 'DB Team C', 'parent_id': cls.org2.id})
        env['sports.team.staff'].create([
            {'team_id': cls.team_c.id, 'partner_id': cls.tp.partner_id.id, 'role': 'therapist'},
            {'team_id': cls.team_c.id, 'partner_id': cls.coach.partner_id.id, 'role': 'coach'},
        ])
        cls.red = _player(env, 'Red', 'Synth', cls.team_a, 'no', 'no')
        cls.shared = _player(env, 'Shared', 'Synth', cls.team_a | cls.team_c, 'no', 'no')
        cls.yellow = _player(env, 'Yellow', 'Synth', cls.team_c, 'no', 'no_contact')
        cls.player_b.write({'match_status': 'no', 'practice_status': 'no'})
        cls.player.write({'match_status': 'yes', 'practice_status': 'yes'})

        Event = env['sports.event']
        today_noon = datetime.combine(fields.Date.today(), time(12, 0))
        now = fields.Datetime.now()

        def _event(name, start, teams, staff=None, state='confirmed', kind='game'):
            return Event.create({
                'name': name, 'event_type': kind,
                'date_start': start, 'date_end': start + timedelta(hours=2),
                'team_ids': [Command.set(teams.ids)],
                'assigned_staff_ids': [Command.set(staff.ids if staff else [])],
                'state': state,
            })

        cls.ev_today = _event('DB Today Game', today_noon, cls.team_a, cls.tp)
        cls.ev_today_cancelled = _event('DB Today Cancelled', today_noon, cls.team_a, cls.tp,
                                        state='cancelled')
        cls.ev_soon = _event('DB Soon Game', now + timedelta(days=3), cls.team_a, cls.tp)
        cls.ev_far = _event('DB Far Game', now + timedelta(days=20), cls.team_c, cls.tp)
        cls.ev_soon_cancelled = _event('DB Soon Cancelled', now + timedelta(days=2), cls.team_a,
                                       cls.tp, state='cancelled')
        cls.ev_b = _event('DB Team B Practice', now + timedelta(days=4), cls.team_b,
                          kind='practice')
        today = fields.Date.today()
        cls.team_a.write({'announcement': 'Synthetic standing note A',
                          'announcement_deadline': today + timedelta(days=5)})
        cls.team_c.write({'announcement': 'Synthetic expired note C',
                          'announcement_deadline': today - timedelta(days=1)})
        cls.team_b.write({'announcement': 'Synthetic note B (not ours)'})

    # -- helpers ------------------------------------------------------------
    def _dash(self, user):
        return self.env['sc.dashboard'].with_user(user)

    def _sections(self, tree):
        return tree.xpath('//section[@data-sc-instance]')

    def _section(self, tree, instance_id):
        found = tree.xpath('//section[@data-sc-instance="%s"]' % instance_id)
        self.assertEqual(len(found), 1, instance_id)
        return found[0]

    def _save(self, user, instances):
        return self._dash(user)._sc_layout_save(instances)

    def _instance(self, user, instance_id):
        return next(i for i in self._dash(user)._sc_layout() if i['id'] == instance_id)
