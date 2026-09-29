"""Synthetic fixtures (public repository: invented names only)."""
import json
from datetime import timedelta

from lxml import html as lxml_html

from odoo import Command, fields
from odoo.tests import HttpCase

SWITCH = 'bemade_sports_clinic.app_shell_enabled'


class BookingsShellCommon(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        portal = env.ref('base.group_portal').id
        tp_g = env.ref('bemade_sports_clinic.group_portal_treatment_professional').id
        cls.tp = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'BK Therapist', 'login': 'bk.tp@example.com', 'password': 'bk-tp-pass',
            'email': 'bk.tp@example.com', 'tz': 'America/Toronto',
            'group_ids': [Command.set([portal, tp_g])],
        })
        cls.client = env['res.partner'].create({'name': 'Quinn Client', 'email': 'quinn@bk.example.com'})
        cls.apt_type = env['appointment.type'].create({
            'appointment_duration': 1,
            'appointment_tz': 'America/Toronto',
            'name': 'BK Assessment',
            'schedule_based_on': 'users',
            'staff_user_ids': [Command.set(cls.tp.ids)],
        })
        now = fields.Datetime.now().replace(minute=0, second=0, microsecond=0)
        Event = env['calendar.event'].with_context(
            no_mail_to_attendees=True, mail_notrack=True, mail_create_nolog=True)

        def _vals(start):
            return {
                'appointment_booker_id': cls.client.id,
                'appointment_type_id': cls.apt_type.id,
                'name': 'BK Assessment - Quinn Client',
                'partner_ids': [Command.link(cls.tp.partner_id.id), Command.link(cls.client.id)],
                'start': start, 'stop': start + timedelta(hours=1),
                'user_id': cls.tp.id,
            }
        cls.booking_soon = Event.create(_vals(now + timedelta(hours=2)))
        cls.booking_past = Event.create(_vals(now - timedelta(days=3)))

    def _switch(self, on):
        self.env['ir.config_parameter'].sudo().set_param(SWITCH, 'True' if on else False)

    def _get(self, url):
        resp = self.url_open(url)
        self.assertEqual(resp.status_code, 200, url)
        return resp.text, lxml_html.fromstring(resp.text)

    @staticmethod
    def _shell(tree):
        nodes = tree.xpath('//*[@data-sc-app-shell]')
        return nodes[0] if nodes else None

    @staticmethod
    def _calendar_props(tree):
        node = tree.xpath('//owl-component[@name="bemade_sports_clinic.sc_calendar"]')[0]
        return json.loads(node.get('props'))
