# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5200 (kit P5): the moved templates' markers were renamed
``data-sc-*`` -> ``data-pk-*`` (search sheet and results, the user guide
links, the « More » rows' rail flag); remove the old ones from the
translated arch values (``strip_translated_attributes``)."""
from odoo.addons.bemade_portal_kit.tools.adopt import strip_translated_attributes

RENAMED = ('data-sc-search-group', 'data-sc-search-player', 'data-sc-search-result', 'data-sc-search-results',
           'data-sc-search-sheet', 'data-sc-search-input', 'data-sc-search-body', 'data-sc-help-home-link',
           'data-sc-in-rail')


def migrate(cr, version):
    strip_translated_attributes(cr, RENAMED)
