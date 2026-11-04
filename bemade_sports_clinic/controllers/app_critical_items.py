"""Task 1677 — the allergy / condition lists and the EpiPen card of the
app's medical popups (therapists only; coaches read).

* ``POST /my/app/medical/item/add`` (patient_id, family, name,
  life_threatening, first_aid_note) adds an item;
* ``POST /my/app/medical/item/<item_id>/save`` (the posted keys among name,
  life_threatening, first_aid_note) changes one;
* ``POST /my/app/medical/item/<item_id>/delete`` removes one;
* ``POST /my/app/medical/<patient_id>/set`` (field, value) saves one field
  of the player's medical block: ``allergy_epipen_state`` (task 1717: yes /
  no), ``allergy_epipen``, ``allergy_epipen_note``,
  ``allergy_none_confirmed``, ``medical_none_confirmed``.

Each answers ``{ok, family, level, tone, refresh, saved_at[, item_id]}`` —
the page refreshes its read fragments in place (the pills, the popups'
header pill and lists, the cards: ``sports.patient:<id>:*``); 403 for anyone
but a therapist with access to the player; 400 ``{error, message}`` for an
invalid value. Writes run as the user (ACL, record rules, the coach block and
the immutability of ``patient_id`` / ``family`` apply).

Replaces the #1654 ``/my/app/critical/*`` routes and the #1653 « Undo »
after « None known » (no level is chosen any more: nothing to undo).
"""
from odoo import _, http
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from odoo.http import request

from ..models.medical_alerts import LEVEL_TONES, UNSET_TONE
from ..models.patient_critical_item import LEVEL_FIELD
from .app_shell import AppShellPortal, _TP_ROLES, _TRUTHY, sc_now_ms

# The player fields the popups save, and the family each belongs to.
SC_MEDICAL_SET_FIELDS = {
    # Task 1717: the Yes / No answer (the boolean stays for old clients).
    'allergy_epipen_state': 'allergy',
    'allergy_epipen': 'allergy',
    'allergy_epipen_note': 'allergy',
    'allergy_none_confirmed': 'allergy',
    'medical_none_confirmed': 'medical_alert',
}
_BOOLEAN_FIELDS = ('allergy_epipen', 'allergy_none_confirmed', 'medical_none_confirmed')


def _truthy(value):
    return str(value or '').strip().lower() in _TRUTHY


class AppCriticalItemsPortal(AppShellPortal):

    def _sc_medical_answer(self, patient, family, **extra):
        patient = patient.sudo()
        patient.invalidate_recordset()
        level = patient[LEVEL_FIELD[family]] or False
        payload = {
            'ok': True,
            'family': family,
            'level': level or 'unset',
            'tone': LEVEL_TONES.get(level, UNSET_TONE),
            'refresh': ['sports.patient:%s:*' % patient.id],
            'saved_at': sc_now_ms(),
        }
        payload.update(extra)
        return self._sc_save_json(payload)

    def _sc_critical_patient(self, patient_id):
        if not (request.env.user._sc_app_roles() & _TP_ROLES):
            raise AccessError(_("Only the therapists can change the medical information."))
        return self._check_access_to_patient(int(patient_id))

    def _sc_item_for(self, item_id):
        """The item (as the user) and its player, or AccessError."""
        item = request.env['sports.patient.critical.item'].browse(int(item_id)).exists()
        if not item:
            raise MissingError(_("Record not found."))
        patient = self._sc_critical_patient(item.sudo().patient_id.id)
        return item, patient

    @staticmethod
    def _sc_invalid(exc):
        return {'error': 'invalid', 'message': str(exc.args[0] if exc.args else exc)}

    @http.route('/my/app/medical/item/add', type='http', auth='user', methods=['POST'], csrf=True,
                multilang=False)
    def sc_medical_item_add(self, patient_id=0, family='allergy', name='', life_threatening='',
                            first_aid_note='', **kw):
        try:
            patient = self._sc_critical_patient(patient_id)
        except (AccessError, MissingError, UserError, ValueError):
            return self._sc_save_json({'error': 'forbidden'}, 403)
        if family not in LEVEL_FIELD:
            return self._sc_save_json({'error': 'invalid', 'message': _("Invalid value.")}, 400)
        name = (name or '').strip()
        if not name:
            return self._sc_save_json({'error': 'invalid', 'message': _("Please fill in all required fields.")}, 400)
        vals = {
            'patient_id': patient.id, 'family': family, 'name': name,
            'life_threatening': _truthy(life_threatening),
        }
        if family == 'medical_alert':
            vals['first_aid_note'] = (first_aid_note or '').strip() or False
        try:
            with request.env.cr.savepoint():
                item = request.env['sports.patient.critical.item'].create(vals)
        except AccessError:
            return self._sc_save_json({'error': 'forbidden'}, 403)
        except (UserError, ValidationError) as exc:
            return self._sc_save_json(self._sc_invalid(exc), 400)
        return self._sc_medical_answer(patient, family, item_id=item.id)

    @http.route('/my/app/medical/item/<int:item_id>/save', type='http', auth='user', methods=['POST'],
                csrf=True, multilang=False)
    def sc_medical_item_save(self, item_id, **post):
        try:
            item, patient = self._sc_item_for(item_id)
        except (AccessError, MissingError, UserError, ValueError):
            return self._sc_save_json({'error': 'forbidden'}, 403)
        family = item.sudo().family
        vals = {}
        if 'name' in post:
            vals['name'] = (post.get('name') or '').strip()
            if not vals['name']:
                return self._sc_save_json({'error': 'invalid', 'message': _("Please fill in all required fields.")}, 400)
        if 'life_threatening' in post:
            vals['life_threatening'] = _truthy(post.get('life_threatening'))
        if 'first_aid_note' in post and family == 'medical_alert':
            vals['first_aid_note'] = (post.get('first_aid_note') or '').strip() or False
        if vals:
            try:
                with request.env.cr.savepoint():
                    item.write(vals)
            except AccessError:
                return self._sc_save_json({'error': 'forbidden'}, 403)
            except (UserError, ValidationError) as exc:
                return self._sc_save_json(self._sc_invalid(exc), 400)
        return self._sc_medical_answer(patient, family, item_id=item.id)

    @http.route('/my/app/medical/item/<int:item_id>/delete', type='http', auth='user', methods=['POST'],
                csrf=True, multilang=False)
    def sc_medical_item_delete(self, item_id, **kw):
        try:
            item, patient = self._sc_item_for(item_id)
        except (AccessError, MissingError, UserError, ValueError):
            return self._sc_save_json({'error': 'forbidden'}, 403)
        family = item.sudo().family
        try:
            with request.env.cr.savepoint():
                item.unlink()
        except AccessError:
            return self._sc_save_json({'error': 'forbidden'}, 403)
        except (UserError, ValidationError) as exc:
            return self._sc_save_json(self._sc_invalid(exc), 400)
        return self._sc_medical_answer(patient, family)

    @http.route('/my/app/medical/<int:patient_id>/set', type='http', auth='user', methods=['POST'],
                csrf=True, multilang=False)
    def sc_medical_set(self, patient_id, field='', value='', **kw):
        if field not in SC_MEDICAL_SET_FIELDS:
            return self._sc_save_json({'error': 'forbidden'}, 403)
        try:
            patient = self._sc_critical_patient(patient_id)
        except (AccessError, MissingError, UserError, ValueError):
            return self._sc_save_json({'error': 'forbidden'}, 403)
        if field == 'allergy_epipen_state':
            written = (value or '').strip()
            if written not in ('yes', 'no'):
                return self._sc_save_json({'error': 'invalid', 'message': _("Invalid value.")}, 400)
        elif field in _BOOLEAN_FIELDS:
            written = _truthy(value)
        else:
            written = (value or '').strip()[:240] or False
        try:
            with request.env.cr.savepoint():
                patient.write({field: written})
        except AccessError:
            return self._sc_save_json({'error': 'forbidden'}, 403)
        except (UserError, ValidationError) as exc:
            return self._sc_save_json(self._sc_invalid(exc), 400)
        return self._sc_medical_answer(patient, SC_MEDICAL_SET_FIELDS[field])
