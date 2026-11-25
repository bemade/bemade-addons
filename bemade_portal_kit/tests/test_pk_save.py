# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5199 (P4a): the save engine, ``POST /my/app/save/<model>/<id>``.

The specs come from the per-database hook ``portal.kit._pk_save_specs()``.
These tests replace the hook's content with ONE synthetic spec on
``res.partner`` (whatever consumer is installed), so they run on a kit-only
Community database. Synthetic fixtures only.

* UC-V1 403 ``{error: forbidden}``: a model without a spec, a field outside
  the spec, a field outside the caller's roles, the spec's ``check``
  refusing, a ``sudo_write`` spec whose ``permission`` refuses. Nothing is
  written.
* UC-V2 400: a missing ``value`` / ``write_date`` (``bad_request``); a write
  hook raising a ValidationError (``invalid`` + its message), nothing left
  behind (savepoint).
* UC-V3 409 ``{conflict, current_value, current_write_date, by}`` when the
  record changed since ``write_date`` AND the field no longer holds
  ``old_value``; no conflict when the field still holds ``old_value``.
* UC-V4 428: the spec's ``confirm`` returns a payload -> answered as is,
  nothing written; the same save posted with ``confirm=1`` is written
  (``confirm`` is not asked again) and the spec's ``context`` reaches the
  write.
* UC-V5 200 shape: ``ok``, ``write_date``, ``value``, ``display``,
  ``refresh`` (the spec's patterns resolved for the record), ``saved_at``
  (server ms), ``live_counts`` when the spec says so, ``hint``, ``also``
  (``also_fields`` / ``also_options``), the write hook's extra keys.
* UC-V6 ``before_write`` state reaches ``after_write``; its dict is merged
  into the 200 payload, or replaces it when it carries ``replace``.
* UC-V7 The route is served by the kit's controller (``pk_app_save``), the
  one handler of the URL.
* UC-V8 Spec validation: every installed spec is valid; an invalid spec
  (sudo_write without permission, unknown refresh field, …) is refused.
"""
import time

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import HttpCase, new_test_user, tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_portal_kit.tools import pk_validate_save_spec

from .common import pk_csrf, pk_hooks

ROLES = {
    'editor': {'groups': ('base.group_user',)},
    'boss': {'groups': ('base.group_system',)},
}
CALLS = []


def _check(ctrl, partner):
    if partner.ref == 'locked':
        raise AccessError('locked')


def _write(ctrl, partner, field, value):
    CALLS.append(('write', partner.env.context.get('pk_test_ctx'), partner.env.context.get('pk_confirmed')))
    if field == 'name':
        value = (value or '').strip()
        if not value:
            raise ValidationError('A name is required.')
        partner.write({'name': value, 'street': 'written along'})
        return {'also_fields': ['street'], 'also_options': {'street': [(1, 'One')]}, 'message': 'soft'}
    partner.write({field: value or False})
    return {}


def _confirm(ctrl, partner, field, value, kw):
    if field == 'name' and partner.name and value != partner.name:
        return {'confirm_rename': True, 'old': partner.name, 'new': value}
    return None


def _context(ctrl, partner, field, kw):
    ctx = {'pk_test_ctx': field}
    if kw.get('confirm') == '1':
        ctx['pk_confirmed'] = True
    return ctx


def _before(ctrl, partner, field):
    return {'before': partner.function or ''}


def _after(ctrl, partner, field, state):
    if field == 'function' and partner.function == 'leave':
        return {'ok': True, 'left': True, 'was': state['before'], 'replace': True}
    if field == 'function':
        return {'was': state['before']}
    return None


def spec():
    return {
        'fields': {'name': ('editor',), 'function': ('editor',), 'website': ('boss',),
                   'street': ('editor',)},
        'check': _check,
        'write': _write,
        'confirm': _confirm,
        'context': _context,
        'before_write': _before,
        'after_write': _after,
        'hint': lambda partner, field: 'hint:%s' % field if field == 'function' else None,
        'refresh': {'*': ['*', 'page:partners:*'], 'name': [lambda p: ['res.partner:%s:title' % p.id]]},
        'live_counts': True,
    }


@tagged('post_install', '-at_install')
class TestPkSave(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.editor = new_test_user(cls.env, login='pk_save_editor', groups='base.group_user,base.group_partner_manager')
        cls.portal = new_test_user(cls.env, login='pk_save_portal', groups='base.group_portal')
        cls.partner = cls.env['res.partner'].create({'name': 'Synthetic Partner', 'function': 'Tester'})

    def setUp(self):
        super().setUp()
        CALLS.clear()
        hooks = pk_hooks(self.env, _pk_roles=lambda _orig: ROLES,
                         _pk_save_specs=lambda _orig: {'res.partner': spec()})
        hooks.__enter__()
        self.addCleanup(hooks.__exit__, None, None, None)
        self.authenticate('pk_save_editor', 'pk_save_editor')

    def _wd(self, record=None):
        record = record or self.partner
        record.invalidate_recordset()
        return fields.Datetime.to_string(record.write_date)

    def _post(self, field, value, record=None, model='res.partner', **extra):
        record = record or self.partner
        data = {'field': field, 'value': value, 'write_date': self._wd(record),
                'csrf_token': self.csrf_token(), **extra}
        data = {k: v for k, v in data.items() if v is not None}
        return self.url_open('/my/app/save/%s/%s' % (model, record.id), data=data, allow_redirects=False)

    def csrf_token(self):
        return pk_csrf(self)

    # -- UC-V1 ------------------------------------------------------------
    def test_forbidden(self):
        cases = [
            ('name', 'X', {'model': 'res.country'}),          # no spec
            ('email', 'x@example.com', {}),                    # field outside the spec
            ('website', 'https://example.com', {}),            # outside the caller's roles
        ]
        for field, value, extra in cases:
            with self.subTest(field=field, **extra):
                record = self.env.ref('base.ca') if extra.get('model') else None
                res = self._post(field, value, record=record, **extra)
                self.assertEqual(res.status_code, 403, res.text)
                self.assertEqual(res.json(), {'error': 'forbidden'})
        self.partner.ref = 'locked'
        res = self._post('function', 'Changed')
        self.assertEqual(res.status_code, 403)
        self.partner.invalidate_recordset()
        self.assertEqual(self.partner.function, 'Tester')
        self.assertFalse(CALLS)

    def test_sudo_write_permission_refused(self):
        def build(_orig):
            s = spec()
            s.update({'sudo_write': True, 'permission': lambda ctrl, partner: False})
            return {'res.partner': s}
        with pk_hooks(self.env, _pk_save_specs=build):
            res = self._post('function', 'Changed')
        self.assertEqual(res.status_code, 403)
        self.assertFalse(CALLS)

    def test_portal_user_without_role(self):
        self.authenticate('pk_save_portal', 'pk_save_portal')
        res = self._post('function', 'Changed')
        self.assertEqual(res.status_code, 403)

    # -- UC-V2 ------------------------------------------------------------
    def test_bad_request_and_invalid(self):
        res = self._post('function', None)
        self.assertEqual((res.status_code, res.json()), (400, {'error': 'bad_request'}))
        res = self.url_open('/my/app/save/res.partner/%s' % self.partner.id, data={
            'field': 'function', 'value': 'x', 'csrf_token': self.csrf_token()}, allow_redirects=False)
        self.assertEqual((res.status_code, res.json()), (400, {'error': 'bad_request'}))
        res = self._post('name', '   ', confirm='1')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json(), {'error': 'invalid', 'message': 'A name is required.'})
        self.partner.invalidate_recordset()
        self.assertEqual(self.partner.name, 'Synthetic Partner')

    # -- UC-V3 ------------------------------------------------------------
    def test_conflict_and_unchanged_field(self):
        stale = '2000-01-01 00:00:00'
        res = self.url_open('/my/app/save/res.partner/%s' % self.partner.id, data={
            'field': 'function', 'value': 'Mine', 'write_date': stale, 'old_value': 'Someone else',
            'csrf_token': self.csrf_token()}, allow_redirects=False)
        self.assertEqual(res.status_code, 409)
        body = res.json()
        self.assertEqual(set(body), {'conflict', 'current_value', 'current_write_date', 'by'})
        self.assertTrue(body['conflict'])
        self.assertEqual(body['current_value'], 'Tester')
        self.assertEqual(body['current_write_date'], self._wd())
        self.assertTrue(body['by'])
        # Stale stamp, but the field still holds what the client saw: saved.
        res = self.url_open('/my/app/save/res.partner/%s' % self.partner.id, data={
            'field': 'function', 'value': 'Mine', 'write_date': stale, 'old_value': 'Tester',
            'csrf_token': self.csrf_token()}, allow_redirects=False)
        self.assertEqual(res.status_code, 200, res.text)
        self.partner.invalidate_recordset()
        self.assertEqual(self.partner.function, 'Mine')

    # -- UC-V4 ------------------------------------------------------------
    def test_confirm_then_confirmed(self):
        res = self._post('name', 'Renamed Partner')
        self.assertEqual(res.status_code, 428)
        self.assertEqual(res.json(), {'confirm_rename': True, 'old': 'Synthetic Partner', 'new': 'Renamed Partner'})
        self.partner.invalidate_recordset()
        self.assertEqual(self.partner.name, 'Synthetic Partner')
        self.assertFalse(CALLS)
        res = self._post('name', 'Renamed Partner', confirm='1')
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(CALLS, [('write', 'name', True)])
        self.partner.invalidate_recordset()
        self.assertEqual(self.partner.name, 'Renamed Partner')

    # -- UC-V5 ------------------------------------------------------------
    def test_success_payload_shape(self):
        before = int(time.time() * 1000)
        res = self._post('name', 'Renamed', confirm='1')
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertTrue(body['ok'])
        self.assertEqual(body['write_date'], self._wd())
        self.assertEqual((body['value'], body['display']), ('Renamed', 'Renamed'))
        self.assertEqual(body['also'], {'street': {
            'value': 'written along', 'display': 'written along', 'options': [['1', 'One']]}})
        self.assertEqual(body['message'], 'soft')
        self.assertTrue(body['live_counts'])
        self.assertNotIn('hint', body)
        pid = self.partner.id
        self.assertEqual(body['refresh'], [
            'res.partner:%s:*' % pid, 'page:partners:*', 'res.partner:%s:title' % pid])
        self.assertGreaterEqual(body['saved_at'], before)
        self.assertLessEqual(body['saved_at'], int(time.time() * 1000))
        res = self._post('function', 'Lead')
        body = res.json()
        self.assertEqual(body['hint'], 'hint:function')
        self.assertEqual(CALLS[-1], ('write', 'function', None))

    # -- UC-V6 ------------------------------------------------------------
    def test_after_write_merges_or_replaces(self):
        body = self._post('function', 'Lead').json()
        self.assertEqual(body['was'], 'Tester')
        self.assertTrue(body['ok'])
        self.assertIn('refresh', body)
        res = self._post('function', 'leave')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {'ok': True, 'left': True, 'was': 'Lead'})

    # -- UC-V7 ------------------------------------------------------------
    def test_route_served_by_the_kit(self):
        from odoo.addons.bemade_portal_kit.controllers.pk_app import PortalKitApp
        rules = [rule for rule in self.env['ir.http'].routing_map().iter_rules()
                 if rule.rule == '/my/app/save/<string:model>/<int:record_id>']
        self.assertEqual(len(rules), 1)
        endpoint = rules[0].endpoint
        self.assertEqual(endpoint.original_endpoint.__name__, 'pk_app_save')
        self.assertIsInstance(endpoint.func.__self__, PortalKitApp)

    # -- UC-V8 ------------------------------------------------------------
    def test_spec_validation(self):
        pk_validate_save_spec('res.partner', spec())
        bad = [
            {'fields': ('name',)},                                                   # no check
            {'fields': ('name',), 'check': _check, 'sudo_write': True, 'write': _write},  # no permission
            {'fields': ('name',), 'check': _check, 'sudo_write': True, 'permission': _check},  # no write
            {'fields': ('name',), 'check': _check, 'refresh': {'other': ['*']}},
            {'fields': ('name',), 'check': _check, 'refresh': {'*': [3]}},
            {'fields': ('name',), 'check': _check, 'confirm': 'yes'},
            {'fields': ('name',), 'check': _check, 'after_write': 'yes'},
        ]
        for case in bad:
            with self.subTest(case=sorted(case)), self.assertRaises(AssertionError):
                pk_validate_save_spec('res.partner', case)

    @mute_logger('odoo.http')
    def test_invalid_spec_is_not_served(self):
        with pk_hooks(self.env, _pk_save_specs=lambda _orig: {'res.partner': {'fields': ('function',)}}):
            res = self._post('function', 'X')
        self.assertEqual(res.status_code, 500)
        self.partner.invalidate_recordset()
        self.assertEqual(self.partner.function, 'Tester')
