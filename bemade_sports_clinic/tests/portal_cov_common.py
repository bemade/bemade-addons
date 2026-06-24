"""Shared HttpCase fixtures for the portal-controller coverage suites.

Not registered in tests/__init__ directly: it has no test methods and is only
imported by the per-controller test modules, so it never runs on its own.
"""
import json
import re
from datetime import datetime, timedelta

from odoo import Command
from odoo.tests import HttpCase


class PortalCovCommon(HttpCase):
    """Builds the portal personas + domain objects the controller routes need."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env

        cls.org = env['res.partner'].create({'name': 'PC Org', 'is_company': True})
        cls.team_a = env['sports.team'].create({'name': 'PC Team A', 'parent_id': cls.org.id})
        cls.team_b = env['sports.team'].create({'name': 'PC Team B', 'parent_id': cls.org.id})

        portal = env.ref('base.group_portal').id
        coach_g = env.ref('bemade_sports_clinic.group_portal_team_coach').id
        tp_g = env.ref('bemade_sports_clinic.group_portal_treatment_professional').id

        cls.coach = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'PC Coach', 'login': 'pc.coach@example.com', 'password': 'pc-coach',
            'group_ids': [Command.set([portal, coach_g])],
        })
        env['sports.team.staff'].create({
            'team_id': cls.team_a.id, 'partner_id': cls.coach.partner_id.id, 'role': 'coach',
        })

        cls.tp = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'PC TP', 'login': 'pc.tp@example.com', 'password': 'pc-tp',
            'group_ids': [Command.set([portal, tp_g])],
        })
        env['sports.team.staff'].create({
            'team_id': cls.team_a.id, 'partner_id': cls.tp.partner_id.id, 'role': 'therapist',
        })

        cls.plain = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'PC Plain', 'login': 'pc.plain@example.com', 'password': 'pc-plain',
            'group_ids': [Command.set([portal])],
        })

        cls.player = env['sports.patient'].create({'first_name': 'Pat', 'last_name': 'One'})
        cls.player.team_ids = [Command.set([cls.team_a.id])]
        cls.player_b = env['sports.patient'].create({'first_name': 'Pat', 'last_name': 'Two'})
        cls.player_b.team_ids = [Command.set([cls.team_b.id])]

        cls.contact = env['sports.patient.contact'].create({
            'patient_id': cls.player.id, 'name': 'Parent One', 'contact_type': 'mother',
        })

        cls.injury = env['sports.patient.injury'].create({
            'patient_id': cls.player.id, 'team_id': cls.team_a.id, 'diagnosis': 'Sprain',
        })
        cls.injury.with_context(mail_notrack=True).write({'stage': 'active'})

        now = datetime(2026, 2, 2, 10, 0)
        cls.event = env['sports.event'].create({
            'name': 'PC Event', 'event_type': 'game',
            'team_ids': [Command.set([cls.team_a.id])],
            'date_start': now, 'date_end': now + timedelta(hours=2),
            'state': 'confirmed',
            'assigned_staff_ids': [Command.set([cls.tp.id])],
        })
        cls.timesheet = env['sports.event.timesheet'].create({
            'event_id': cls.event.id, 'user_id': cls.tp.id,
        })

        # A few activities for the task/activity portal routes.
        todo = env.ref('mail.mail_activity_data_todo')
        def _act(model, res_id, summary):
            return env['mail.activity'].create({
                'res_model_id': env['ir.model']._get(model).id,
                'res_id': res_id, 'activity_type_id': todo.id,
                'summary': summary, 'user_id': cls.tp.id,
            })
        cls.act_player = _act('sports.patient', cls.player.id, 'Player task')
        cls.act_injury = _act('sports.patient.injury', cls.injury.id, 'Injury task')
        cls.act_team = _act('sports.team', cls.team_a.id, 'Team task')
        cls.act_event = _act('sports.event', cls.event.id, 'Event task')

    def _login_coach(self):
        self.authenticate('pc.coach@example.com', 'pc-coach')

    def _login_tp(self):
        self.authenticate('pc.tp@example.com', 'pc-tp')

    def _login_plain(self):
        self.authenticate('pc.plain@example.com', 'pc-plain')

    def _csrf(self):
        """Scrape a CSRF token from a rendered portal page (19.0 has no
        HttpCase.csrf_token() helper). Must be called while authenticated."""
        resp = self.url_open('/my')
        m = re.search(r'csrf_token:\s*"([^"]+)"', resp.text)
        return m.group(1) if m else ''

    def _jsonrpc(self, url, **params):
        """POST a JSON-RPC 2.0 'call' to a type='jsonrpc' route; return result."""
        resp = self.url_open(
            url,
            data=json.dumps({'jsonrpc': '2.0', 'method': 'call', 'params': params}),
            headers={'Content-Type': 'application/json'},
        )
        return resp.json().get('result')
