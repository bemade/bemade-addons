# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5345 (kit P3c2): the layout's, the user menu's and the shell
components' markers were renamed ``data-sc-*`` -> ``data-pk-*``. A marker
inside a translated term (e.g. a switch's reason line translated with its
text) keeps the old attribute, dead, next to the new one in the non-English
arch after the upgrade. Remove the old ones from the translations
(``strip_translated_attributes``; the source is already clean).

``data-sc-action``, ``data-sc-nav-key`` and ``data-sc-activity-clock`` /
``-overdue`` keep other meanings in the clinic: they are not listed.
"""
from odoo.addons.bemade_portal_kit.tools.adopt import strip_translated_attributes

RENAMED = tuple('data-sc-%s' % name for name in (
    'hide-done', 'top', 'pref', 'theme-switch', 'user-menu-head', 'user-menu', 'sort', 'card-icons',
    'card-archive', 'card-trash', 'history-state', 'scope', 'overdue', 'switch-locked', 'switch-reason',
    'confirm-submit', 'title-split', 'title-link', 'row-links', 'row-link-plain', 'row-link',
))


def migrate(cr, version):
    strip_translated_attributes(cr, RENAMED)
