# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5382 (kit P4c3): the autosave field's markers and the picker hook
were renamed ``data-sc-*`` -> ``data-pk-*``. Some sit inside translated
terms (a select carrying ``data-sc-picker`` translated with its options):
the upgrade keeps the old attribute, dead, next to the new one in the
non-English arch. Remove the old ones from the translations
(``strip_translated_attributes``; the source is already clean).

``data-sc-state`` keeps its other meanings (a worklist row, a timesheet
row): it is not listed.
"""
from odoo.addons.bemade_portal_kit.tools.adopt import strip_translated_attributes

RENAMED = tuple('data-sc-%s' % name for name in (
    'org-confirm-box', 'org-confirm', 'org-cancel', 'tags-typed-error', 'tags-group-notice', 'tags-index',
    'tags-open', 'picker-key', 'picker', 'autosave', 'restored', 'replace', 'teams', 'player', 'field', 'value',
))


def migrate(cr, version):
    strip_translated_attributes(cr, RENAMED)
