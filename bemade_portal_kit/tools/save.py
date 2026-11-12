# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5199 (P4a): the save engine's specs — WHAT may be saved field by
field through ``POST /my/app/save/<model>/<id>``, and BY WHOM.

The specs come from the per-database hook ``portal.kit._pk_save_specs()``
(``{model: spec}``, extended with ``super()``). A spec::

    {
        'fields': {'field_a': ROLES, ...},   # per-role allowlist: the field is
                                             # refused (403) unless the caller
                                             # holds one of ROLES (the kit's
                                             # roles, res.users._pk_roles()).
                                             # A plain tuple of names: any
                                             # caller the check lets through.
        'check': callable(ctrl, record),     # MANDATORY; raises AccessError /
                                             # MissingError (403) or UserError
                                             # (400) to refuse.
        'write': callable(ctrl, record, field, value) -> dict | None
                                             # optional write hook (validation,
                                             # pairs, normalisation). Raises
                                             # UserError / ValidationError ->
                                             # 400. Its dict: extra payload
                                             # keys (``message``), plus
                                             # ``also_fields`` (other fields
                                             # it set: answered under ``also``
                                             # as {value, display}),
                                             # ``also_options`` ({field:
                                             # [(key, label)]}),
                                             # ``also_disabled`` ({field:
                                             # bool}) and ``propose_context``
                                             # (context for ``propose``).
        'read': callable(record, field) -> value
                                             # optional, for VIRTUAL fields
                                             # (not on the model) or a custom
                                             # input value.
        'display': callable(record, field) -> str | None
                                             # optional: the read view's text
                                             # (None = the default display).
        'hint': callable(record, field) -> str | None
                                             # optional: the field's fresh
                                             # « updated on … by … » stamp,
                                             # answered as ``hint``.
        'refresh': {field | '*': [entry, ...]}
                                             # the READ FRAGMENTS a save of
                                             # ``field`` makes stale (see
                                             # tools/fragments.py), answered as
                                             # ``refresh``.
        'propose': callable(record, field) -> dict | None
                                             # a follow-up proposal after the
                                             # save, answered as ``propose``
                                             # (PortalKitApp._pk_save_proposal;
                                             # a failure never fails the save).
        'live_counts': True,                 # the save also refreshes the
                                             # page's live counters.
        'sudo_write': True,                  # the hook writes as sudo …
        'permission': callable(ctrl, record) -> bool,
                                             # … which REQUIRES this callable,
                                             # checked before any write.
        'context': callable(ctrl, record, field, kw) -> dict | None
                                             # the context the record is
                                             # confirmed and written with
                                             # (``kw``: the posted extras,
                                             # e.g. ``confirm``).
        'confirm': callable(ctrl, record, field, value, kw) -> dict | None
                                             # a dict = this save needs an
                                             # explicit confirmation: answered
                                             # as is with 428, nothing written.
                                             # The client re-posts the same
                                             # save with ``confirm=1``; then
                                             # ``confirm`` is not asked again.
        'before_write': callable(ctrl, record, field) -> state
                                             # what to know before the write
                                             # (e.g. the record's teams) …
        'after_write': callable(ctrl, record, field, state) -> dict | None
                                             # … for this hook, called right
                                             # after the write, BEFORE the
                                             # record is read back: a dict is
                                             # merged into the 200 payload, or
                                             # REPLACES it when it carries
                                             # ``replace: True`` (e.g. the
                                             # caller lost access to the
                                             # record: nothing is read back).
    }

The write runs AS THE USER unless the spec declares ``sudo_write`` (only
where the user genuinely lacks the ACL for the write): ACLs, record rules
and the models' own write guards apply on top of ``check``. A field outside
the caller's roles is refused even when the ORM would allow it.

``pk_validate_save_spec`` asserts the rules above; the route validates the
spec it uses, the kit's tests validate every installed spec.
"""
from datetime import date

from odoo import _, fields
from odoo.exceptions import ValidationError

PK_MIN_YEAR = 1900
PK_MAX_YEAR = 9999
_CALLABLE_KEYS = (
    'write', 'read', 'display', 'hint', 'propose', 'permission', 'context',
    'confirm', 'before_write', 'after_write',
)


def pk_validate_save_spec(model, spec):
    """Assert that ``spec`` is a valid save spec of ``model``."""
    assert spec.get('fields'), "%s: 'fields' is mandatory" % model
    assert callable(spec.get('check')), "%s: 'check' is mandatory" % model
    for key in _CALLABLE_KEYS:
        assert spec.get(key) is None or callable(spec[key]), (
            "%s: %r must be callable" % (model, key))
    if spec.get('sudo_write'):
        assert callable(spec.get('permission')), (
            "%s: a sudo_write spec requires a 'permission' callable" % model)
        assert callable(spec.get('write')), (
            "%s: a sudo_write spec requires its 'write' hook" % model)
    for field, entries in (spec.get('refresh') or {}).items():
        assert field == '*' or field in spec['fields'], (
            "%s: 'refresh' names an unknown field %r" % (model, field))
        assert all(callable(entry) or isinstance(entry, str) for entry in entries), (
            "%s: a 'refresh' entry is a key pattern or a callable" % model)


def pk_parse_date(value):
    """A posted date (``YYYY-MM-DD``) as a ``date``; empty -> False. A
    malformed value or a year outside 1900..9999 raises a ValidationError
    (« Please enter a valid date. »), never the ORM's generic error."""
    if value in ('', None, False):
        return False
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return False
    try:
        day = fields.Date.to_date(value)
    except (TypeError, ValueError):
        raise ValidationError(_("Please enter a valid date.")) from None
    if not isinstance(day, date) or not PK_MIN_YEAR <= day.year <= PK_MAX_YEAR:
        raise ValidationError(_("Please enter a valid date."))
    return day


def pk_deadline_in_past(day, current, user):
    """True when ``day`` is a NEW due date (not the stored ``current`` one: an
    overdue activity saved without touching its date is fine) before
    ``user``'s today (their timezone)."""
    if not day or day == current:
        return False
    return day < fields.Date.context_today(user)
