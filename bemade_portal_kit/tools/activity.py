# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5199 (P4a): the kit's save spec of ``mail.activity`` — an activity's
summary, due date, assignee and note, edited in place.

Who may act on an activity and to whom it may be assigned are two hooks of
``portal.kit`` a consumer overrides with its own rules:

* ``_pk_activity_can_act(activity)``: default = the user's own write right
  on the activity (ACL + record rules);
* ``_pk_activity_assignable_users(activity)``: default = the internal users
  and the user themself.

The write runs as sudo AFTER ``_pk_activity_can_act`` (``sudo_write``), so a
consumer may let roles without the ACL act (e.g. a read-only ACL). A new due
date is never in the past (the user's today). Read and display go through
sudo: the check above is the authorization.
"""
from odoo import _, fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import html2plaintext, plaintext2html

from .save import pk_deadline_in_past, pk_parse_date

ACTIVITY_FIELDS = ('summary', 'date_deadline', 'user_id', 'note')


def _can_act(activity):
    return bool(activity.env['portal.kit']._pk_activity_can_act(activity))


def _check(ctrl, activity):
    if not _can_act(activity):
        raise AccessError(_("You do not have access to this activity."))


def _permission(ctrl, activity):
    return _can_act(activity)


def _write(ctrl, activity, field, value):
    record = activity.sudo()
    if field == 'summary':
        value = (value or '').strip()
        if not value:
            raise ValidationError(_("Please fill in all required fields."))
        record.write({'summary': value})
    elif field == 'date_deadline':
        day = pk_parse_date(value)
        if not day:
            raise ValidationError(_("Please fill in all required fields."))
        if pk_deadline_in_past(day, record.date_deadline, activity.env.user):
            raise ValidationError(_("The due date cannot be in the past."))
        record.write({'date_deadline': day})
    elif field == 'note':
        record.write({'note': plaintext2html(value) if (value or '').strip() else False})
    elif field == 'user_id':
        try:
            user = activity.env['res.users'].browse(int(value))
        except (TypeError, ValueError):
            user = activity.env['res.users']
        if user != record.user_id:
            allowed = activity.env['portal.kit']._pk_activity_assignable_users(activity)
            if not user or user.id not in allowed.ids:
                raise ValidationError(_("You cannot assign this activity to that user."))
            record.write({'user_id': user.id})
    return {}


def _read(activity, field):
    activity = activity.sudo()
    if field == 'note':
        return html2plaintext(activity.note or '').strip()
    if field == 'user_id':
        return activity.user_id.id or False
    if field == 'date_deadline':
        return fields.Date.to_string(activity.date_deadline) if activity.date_deadline else ''
    return activity[field] or ''


def _display(activity, field):
    activity = activity.sudo()
    if field == 'note':
        return html2plaintext(activity.note or '').strip()
    if field == 'user_id':
        return activity.user_id.name or ''
    return None


def pk_activity_save_spec():
    """A fresh copy of the kit's ``mail.activity`` spec."""
    return {
        'fields': ACTIVITY_FIELDS,
        'check': _check,
        'write': _write,
        'read': _read,
        'display': _display,
        'sudo_write': True,
        'permission': _permission,
        # Title, state chip, note; the live counters (overdue badge).
        'refresh': {'*': ['*']},
        'live_counts': True,
    }
