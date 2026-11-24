# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5370 (kit P4b): the form guard's, the pills' and the lazy edit's
markers were renamed ``data-sc-*`` -> ``data-pk-*``. Some sit inside
translated terms (``<span data-sc-guard-msg="…">``, translated with its
markup): the upgrade keeps the old attribute, dead, next to the new one in
the French arch. Remove the old ones from the translations
(``strip_translated_attributes``; the source is already clean).
"""
from odoo.addons.bemade_portal_kit.tools.adopt import strip_translated_attributes

RENAMED = tuple('data-sc-%s' % name for name in (
    'guard', 'guard-mode', 'guard-rules', 'guard-msg', 'guard-texts', 'guard-submit', 'guard-reason',
    'guard-error', 'guard-block', 'guard-field-error', 'guard-invalid', 'guard-missing', 'guard-generic',
    'guard-offline', 'required', 'flash-error', 'error-for', 'field-error', 'pill-select', 'pill-key',
    'pill-value', 'pill-post', 'pill-action', 'pill-from', 'pill-readonly', 'model', 'record-id',
    'write-date', 'old-value', 'undo-message', 'lazy-edit', 'lazy-edit-host', 'lazy-mounted',
))


def migrate(cr, version):
    strip_translated_attributes(cr, RENAMED)
