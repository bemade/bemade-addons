# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""The dashboard's stored names, adopted from the first consumer.

Task 5202 (kit P7): the section frame and the configure sheet were the
first consumer's templates: their ``ir.ui.view`` records keep their ids
(translations, inheriting views), only the external id and key move here
(``bemade_portal_kit.tools.adopt.adopt_views`` with ``target``). The
users' layouts move with their column, in place, byte for byte
(``bemade_portal_kit.tools.data_moves.move_columns`` with ``target``):
the stored JSON is never rewritten. The old module and names below are
historical data, the one place this addon names the first consumer.

Entry points: this addon's ``pre_init_hook`` (it is installed as a new
dependency of the consumer's upgrade, before its models create the new
column) and the consumer's own pre-migration (idempotent; a no-op once
done).
"""
DASH = 'bemade_portal_kit_dashboard'

# (old module, old name, new name)
DASH_ADOPTED_VIEWS = (
    ('bemade_sports_clinic', 'sc_dw_section', 'pk_dash_section'),
    ('bemade_sports_clinic', 'sc_app_dashboard_configure', 'pk_dash_configure'),
)

# (table, old column, new column, model, old module)
DASH_MOVED_COLUMNS = (
    ('res_users', 'sc_dashboard_layout', 'pk_dashboard_layout', 'res.users', 'bemade_sports_clinic'),
)


def adopt_dashboard(cr):
    """Every P7 move (views, then the layout column); idempotent."""
    from odoo.addons.bemade_portal_kit.tools.adopt import adopt_views
    from odoo.addons.bemade_portal_kit.tools.data_moves import move_columns
    return {
        'views': adopt_views(cr, DASH_ADOPTED_VIEWS, target=DASH),
        'columns': move_columns(cr, DASH_MOVED_COLUMNS, target=DASH),
    }
