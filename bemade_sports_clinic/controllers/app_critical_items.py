"""Task 1654 — add / remove a player's critical medical items from the app's
medical popups (therapists only; coaches read).

``POST /my/app/critical/add`` (patient_id, family, name, epipen, action) and
``POST /my/app/critical/<item_id>/delete`` answer like a save of the family's
level: ``{ok, value, display, write_date, also: {epipen…}, refresh,
saved_at}`` so the popup's level field, the pills, the cards and the item
list follow in place (fragments ``sports.patient:<id>:*``); 403 for anyone
but a therapist with access to the player; 400 ``{error, message}`` for an
invalid item.
"""
from odoo import _, fields, http
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from odoo.http import request

from ..models.patient_critical_item import LEVEL_FIELD
from .app_shell import AppShellPortal, _TP_ROLES, sc_now_ms, sc_refresh_patterns


class AppCriticalItemsPortal(AppShellPortal):

    def _sc_critical_answer(self, patient, family):
        patient.invalidate_recordset()
        level_field = LEVEL_FIELD[family]
        payload = {
            'ok': True,
            'field': level_field,
            'value': self._sc_save_value(patient, level_field),
            'display': self._sc_save_display(patient, level_field),
            'write_date': fields.Datetime.to_string(patient.sudo().write_date),
            'refresh': sc_refresh_patterns('sports.patient', patient, level_field)
            or ['sports.patient:%s:*' % patient.id],
            'saved_at': sc_now_ms(),
        }
        # The family's other fields follow too (their value, their write
        # date — no stale-write conflict on the next save — and their lock:
        # « None known » after the last item of a family without details).
        locked = patient.sudo()[level_field] == 'none'
        others = ('allergy_epipen', 'allergy_details') if family == 'allergy' else ('medical_alert_details',)
        payload['also'] = {name: {
            'value': self._sc_save_value(patient, name),
            'display': self._sc_save_display(patient, name),
            'disabled': locked,
        } for name in others}
        return payload

    def _sc_critical_patient(self, patient_id):
        if not (request.env.user._sc_app_roles() & _TP_ROLES):
            raise AccessError(_("Only the therapists can change the medical information."))
        return self._check_access_to_patient(int(patient_id))

    @http.route('/my/app/critical/add', type='http', auth='user', methods=['POST'], csrf=True)
    def sc_critical_add(self, patient_id=0, family='allergy', name='', epipen='', action='', **kw):
        try:
            patient = self._sc_critical_patient(patient_id)
        except (AccessError, MissingError, UserError, ValueError):
            return self._sc_save_json({'error': 'forbidden'}, 403)
        if family not in LEVEL_FIELD:
            return self._sc_save_json({'error': 'invalid', 'message': _("Invalid value.")}, 400)
        name = (name or '').strip()
        if not name:
            return self._sc_save_json({'error': 'invalid', 'message': _("Please fill in all required fields.")}, 400)
        try:
            with request.env.cr.savepoint():
                request.env['sports.patient.critical.item'].create({
                    'patient_id': patient.id, 'family': family, 'name': name,
                    'epipen': family == 'allergy' and str(epipen).lower() in ('1', 'on', 'true', 'yes'),
                    'action': (action or '').strip() or False,
                })
        except (UserError, ValidationError) as exc:
            return self._sc_save_json({'error': 'invalid', 'message': str(exc.args[0] if exc.args else exc)}, 400)
        return self._sc_save_json(self._sc_critical_answer(patient, family))

    @http.route('/my/app/critical/<int:item_id>/delete', type='http', auth='user', methods=['POST'], csrf=True)
    def sc_critical_delete(self, item_id, **kw):
        item = request.env['sports.patient.critical.item'].browse(item_id).exists()
        if not item:
            return self._sc_save_json({'error': 'forbidden'}, 403)
        try:
            patient = self._sc_critical_patient(item.sudo().patient_id.id)
        except (AccessError, MissingError, UserError, ValueError):
            return self._sc_save_json({'error': 'forbidden'}, 403)
        family = item.sudo().family
        try:
            with request.env.cr.savepoint():
                item.unlink()
        except (AccessError, UserError, ValidationError) as exc:
            return self._sc_save_json({'error': 'invalid', 'message': str(exc.args[0] if exc.args else exc)}, 400)
        return self._sc_save_json(self._sc_critical_answer(patient, family))
