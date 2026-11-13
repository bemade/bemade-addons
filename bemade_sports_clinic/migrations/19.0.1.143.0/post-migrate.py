# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5381 (kit P4c2): the edit cards', sheets', tabs', lazy load's and
clamps' markers were renamed ``data-sc-*`` -> ``data-pk-*``. Some sit inside
translated terms (a link or button carrying ``data-sc-sheet-open`` translated
with its markup): the upgrade keeps the old attribute, dead, next to the new
one in the non-English arch. Remove the old ones from the translations
(``strip_translated_attributes``; the source is already clean).
"""
from odoo.addons.bemade_portal_kit.tools.adopt import strip_translated_attributes

RENAMED = tuple('data-sc-%s' % name for name in (
    'edit-toggle-done', 'edit-toggle', 'edit-view', 'edit-open-on-load', 'edit-open', 'edit-for', 'edit-only',
    'edit-done-label', 'tab-panel', 'tab-aliases', 'tabs', 'tab', 'sheet-open-on-load', 'sheet-open',
    'sheet-close', 'sheet-url', 'sheet-refetch', 'lazy-url', 'lazy-fresh', 'lazy-filled', 'row-expand',
    'clamp-more', 'clamp-less', 'clamp-sep', 'clamp-meta', 'clamp-open', 'clamp-ready', 'clamp',
    'draft-clear', 'display-hide-empty', 'display',
))


def migrate(cr, version):
    strip_translated_attributes(cr, RENAMED)
