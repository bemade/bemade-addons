# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5199 (P4a): the kit's app controller — the save engine
(``POST /my/app/save/<model>/<id>``) and the screen refresh (fragment
answers).

A consumer's portal controller INHERITS ``PortalKitApp`` (not
``CustomerPortal`` directly): the route then resolves to one handler whose
``self`` is the consumer's controller, so the spec callables receive it as
``ctrl`` with the consumer's own access methods. A consumer never declares
the route again.

Specs: ``portal.kit._pk_save_specs()`` (``tools/save.py`` documents them).
Fragments: ``tools/fragments.py``.
"""
import logging

from odoo import _, fields, http
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from odoo.http import request
from odoo.tools import format_date, format_datetime

from odoo.addons.portal.controllers.portal import CustomerPortal

from ..tools import (
    PK_FRAGMENTS_HEADER, PK_GUARD_HEADER, pk_extract_fragments, pk_now_ms, pk_parse_fragment_keys,
    pk_validate_save_spec,
)
from ..tools.registry import pk_freeze

_logger = logging.getLogger(__name__)

_TEXT_TYPES = ('char', 'text', 'html')


class PortalKitApp(CustomerPortal):

    # ------------------------------------------------------------------
    # Screen refresh (read fragments)
    # ------------------------------------------------------------------
    @staticmethod
    def _pk_fragment_keys():
        """The fragment keys a request asks for (``X-Pk-Fragments``), or None
        for a normal page request."""
        try:
            raw = request.httprequest.headers.get(PK_FRAGMENTS_HEADER)
        except RuntimeError:  # no request
            return None
        return pk_parse_fragment_keys(raw)

    @staticmethod
    def _pk_fragments_response(response, keys, rendered_at=None):
        """The fragment answer of a page: ``response`` (the page's lazy
        render, as for a reload) reduced to the nodes of ``keys`` — JSON
        ``{fragments, missing, title, rendered_at}``, never cached. The
        ``portal.kit._pk_fragment_fillers()`` run on what was found."""
        found, title = pk_extract_fragments(response.render(), keys)
        for filler in request.env['portal.kit']._pk_fragment_fillers():
            filler(found, keys)
        answer = request.make_json_response({
            'fragments': found,
            'missing': [key for key in keys if key not in found],
            'title': title,
            'rendered_at': rendered_at or pk_now_ms(),
        })
        answer.headers['Cache-Control'] = 'no-store'
        answer.headers['Vary'] = PK_FRAGMENTS_HEADER
        return answer

    @classmethod
    def _pk_render(cls, template, values):
        """A page that answers fragments: the page itself, or — asked with
        ``X-Pk-Fragments`` — the requested regions of the same render.
        ``values['pk_rendered_at']`` (set here when absent) is the render
        stamp the shell root carries in ``data-pk-rendered-at``."""
        values.setdefault('pk_rendered_at', pk_now_ms())
        response = request.render(template, values)
        keys = cls._pk_fragment_keys()
        if keys is None:
            return response
        return cls._pk_fragments_response(response, keys, values['pk_rendered_at'])

    # ------------------------------------------------------------------
    # Form guard (task 5370, P4b)
    # ------------------------------------------------------------------
    @staticmethod
    def _pk_guard_probe():
        """Is this request a guarded form's fetch? (``pk_form_guard`` sends
        ``X-Pk-Guard: 1`` on its POST, kept across the redirect.) A page then
        peeks at its one-time session state instead of popping it."""
        try:
            return request.httprequest.headers.get(PK_GUARD_HEADER) == '1'
        except RuntimeError:  # no request
            return False

    # ------------------------------------------------------------------
    # Save engine
    # ------------------------------------------------------------------
    @staticmethod
    def _pk_save_json(payload, status=200):
        return request.make_json_response(payload, status=status)

    @staticmethod
    def _pk_save_spec(model):
        """The save spec of ``model`` in this database (validated), or None."""
        spec = request.env['portal.kit'].pk_save_spec(model)
        if spec is not None:
            pk_validate_save_spec(model, spec)
        return spec

    @staticmethod
    def _pk_save_value(record, name, raw=False):
        """The value an input shows for ``record.name`` (the spec's ``read``
        unless ``raw``): a many2one's id, a date as a string."""
        spec = record.env['portal.kit'].pk_save_spec(record._name) or pk_freeze({})
        if not raw and spec.get('read'):
            return spec['read'](record, name)
        value = record[name]
        field = record._fields[name]
        if field.type == 'many2one':
            return value.id or False
        if field.type in ('date', 'datetime'):
            return field.to_string(value) if value else False
        return value

    @staticmethod
    def _pk_save_display(record, name):
        """The saved value as a reader sees it (a card's read view updates in
        place after a save): a name for a many2one, a label for a selection,
        a formatted date; '' when empty. The spec's ``display`` first."""
        spec = record.env['portal.kit'].pk_save_spec(record._name) or pk_freeze({})
        if spec.get('display'):
            shown = spec['display'](record, name)
            if shown is not None:
                return shown
        field = record._fields.get(name)
        if field is None:
            return ''
        value = record[name]
        if not value:
            return ''
        if field.type == 'many2one':
            # The plain name, as the select options show it.
            value = value.sudo()
            return (value.name if 'name' in value._fields else value.display_name) or ''
        if field.type == 'selection':
            return dict(field._description_selection(record.env)).get(value, '')
        if field.type == 'date':
            return format_date(record.env, value)
        if field.type == 'datetime':
            return format_datetime(record.env, value)
        return str(value)

    @classmethod
    def _pk_field_unchanged(cls, record, field, old_value):
        """Does ``record.field`` still hold what the client last saw?"""
        if old_value is None:
            return False
        current = cls._pk_save_value(record, field)
        if current is False or current is None:
            current = ''
        return str(current).strip() == str(old_value).strip()

    @staticmethod
    def _pk_save_allowed(spec, field):
        """Is ``field`` in the spec's allowlist for the CALLER's roles?"""
        allowed = spec.get('fields') or ()
        if field not in allowed:
            return False
        if isinstance(allowed, dict):
            return bool(request.env.user._pk_roles() & frozenset(allowed[field]))
        return True

    @staticmethod
    def _pk_save_options(pairs):
        """[(key, label, …)] -> JSON-safe [[str(key), str(label), …]]."""
        return [[str(part) for part in option] for option in pairs]

    def _pk_save_proposal(self, spec, record, field):
        """The spec's follow-up proposal for this save, or None. A builder
        failure never fails the save it follows. A consumer may restrict
        who gets proposals by overriding this method."""
        if not spec.get('propose'):
            return None
        try:
            return spec['propose'](record, field) or None
        except Exception:  # noqa: BLE001 — a proposal is a convenience only
            _logger.exception("Follow-up proposal failed for %s.%s", record._name, field)
            return None

    @http.route(['/my/app/save/<string:model>/<int:record_id>'], type='http', auth='user',
                methods=['POST'], csrf=True, multilang=False)
    def pk_app_save(self, model, record_id, field=None, value=None, write_date=None,
                    old_value=None, **kw):
        """Save ONE field of ONE record, as the user.

        Body (form-encoded, CSRF enforced): ``field``, ``value``,
        ``write_date`` (the record's stamp the client last saw), optional
        ``old_value`` (the FIELD value the client last saw: a record written
        since, whose field still holds ``old_value``, is not a conflict) and
        ``confirm=1`` (the confirmation a 428 asked for). Answers JSON:

        * 200 ``{ok, write_date, value, display[, also, hint, refresh,
          saved_at, live_counts, propose, message, …]}`` — saved;
        * 409 ``{conflict, current_value, current_write_date, by}`` — the
          field changed since (nothing written);
        * 403 ``{error: forbidden}`` — no spec for the model, a field
          outside the spec or the caller's roles, the spec's check /
          permission refused, or the ORM refused the write;
        * 400 ``{error: bad_request}`` — missing parameters;
          ``{error: invalid, message}`` — an invalid value (nothing
          written);
        * 428 — the spec's ``confirm`` payload (nothing written until the
          same save is re-posted with ``confirm=1``).
        """
        spec = self._pk_save_spec(model)
        if not spec or not field or not self._pk_save_allowed(spec, field):
            return self._pk_save_json({'error': 'forbidden'}, 403)
        if value is None or not write_date:
            return self._pk_save_json({'error': 'bad_request'}, 400)
        record = request.env[model].browse(record_id)
        try:
            if not record.exists():
                raise MissingError(_("Record not found."))
            spec['check'](self, record)
            if spec.get('sudo_write') and not spec['permission'](self, record):
                raise AccessError(_("You cannot edit this record."))
            # The stamp, the stale check and the 409 read through sudo: the
            # role allowlist and the check passed above, and a group-
            # restricted field (or, for a sudo_write spec, the record itself)
            # may not be readable through the ORM.
            current = fields.Datetime.to_string(record.sudo().write_date)
            if current != write_date and not self._pk_field_unchanged(record.sudo(), field, old_value):
                return self._pk_save_json({
                    'conflict': True,
                    'current_value': self._pk_save_value(record.sudo(), field),
                    'current_write_date': current,
                    'by': record.sudo().write_uid.name or '',
                }, 409)
            if spec.get('context'):
                context = spec['context'](self, record, field, kw)
                if context:
                    record = record.with_context(**context)
            if spec.get('confirm') and kw.get('confirm') != '1':
                refusal = spec['confirm'](self, record, field, value, kw)
                if refusal:
                    return self._pk_save_json(refusal, 428)
            state = spec['before_write'](self, record, field) if spec.get('before_write') else None
            extra = {}
            # A refused / invalid write leaves nothing behind (a hook may
            # write more than one field).
            with request.env.cr.savepoint():
                if spec.get('write'):
                    extra = spec['write'](self, record, field, value) or {}
                else:
                    if value == '' and record._fields[field].type not in _TEXT_TYPES:
                        value = False
                    record.write({field: value})
                record.flush_recordset()
            record.invalidate_recordset()
            after = spec['after_write'](self, record, field, state) if spec.get('after_write') else None
            if after and after.get('replace'):
                answer = dict(after)
                answer.pop('replace')
                return self._pk_save_json(answer)
            payload = {
                'ok': True,
                'write_date': fields.Datetime.to_string(record.sudo().write_date),
                'value': self._pk_save_value(record, field),
                'display': self._pk_save_display(record, field),
            }
            # Other fields the write hook set along, so the page updates them
            # in place: {field: {value, display[, options, disabled]}}.
            also = extra.pop('also_fields', None) or ()
            also_options = extra.pop('also_options', None) or {}
            also_disabled = extra.pop('also_disabled', None) or {}
            if also:
                payload['also'] = {name: {
                    'value': self._pk_save_value(record, name),
                    'display': self._pk_save_display(record, name),
                } for name in also}
                for name, options in also_options.items():
                    if name in payload['also']:
                        payload['also'][name]['options'] = self._pk_save_options(options)
                for name, disabled in also_disabled.items():
                    if name in payload['also']:
                        payload['also'][name]['disabled'] = bool(disabled)
            hint = spec['hint'](record, field) if spec.get('hint') else None
            if hint is not None:
                payload['hint'] = hint
            # The read fragments this save makes stale, the server time of
            # the save (the « back » check) and the live counters.
            payload['refresh'] = request.env['portal.kit'].pk_refresh_patterns(record, field)
            payload['saved_at'] = pk_now_ms()
            if spec.get('live_counts'):
                payload['live_counts'] = True
            # A follow-up proposal: never blocking (the field is saved). What
            # the write hook knew before writing reaches the builder.
            propose_context = extra.pop('propose_context', None)
            proposal = self._pk_save_proposal(
                spec, record.with_context(**propose_context) if propose_context else record, field)
            if proposal:
                payload['propose'] = proposal
            payload.update(extra)
            if after:
                payload.update(after)
            return self._pk_save_json(payload)
        except (AccessError, MissingError):
            return self._pk_save_json({'error': 'forbidden'}, 403)
        except (UserError, ValidationError, ValueError) as exc:
            message = exc.args[0] if getattr(exc, 'args', None) else str(exc)
            return self._pk_save_json({'error': 'invalid', 'message': str(message)}, 400)
