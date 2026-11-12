# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""View xmlid adoption: a consumer's generic template moves into the kit.

Task 5369 (kit P3c1). A template that moves from a consumer to the kit keeps
its ``ir.ui.view`` record (same id): the views that inherit it, its
translations (``arch_db``, same row) and any website copy stay attached. Only
its external id changes, ``<consumer>.<old_name>`` ->
``bemade_portal_kit.<new_name>``, and its ``key`` with it (a ``t-call``
resolves the key first, then the external id).

Why a migration, and why from BOTH modules:

* the kit's data file declares ``bemade_portal_kit.<new_name>``; the loader
  looks the external id up by module and name, so without the rename BEFORE
  the kit's data load it would create a second view, and the consumer's
  upgrade would then delete the old one (``_process_end``: a record of an
  updated module that its data no longer declares), with its translations
  and inheriting views. Hence a PRE-migration;
* ``-u <consumer>`` alone does not upgrade the kit (an upgrade adds the
  dependents of a module, not its dependencies), so the consumer's own
  pre-migration must adopt the views too, or ``_process_end`` deletes them.
  When the kit was not upgraded in the same run, the consumer's
  pre-migration also loads the kit's view files (``load_kit_views``), so
  that the kit's new views (``pk_icon_extra``, which the consumer inherits)
  exist before the consumer's data refers to them.

``adopt_views`` is idempotent: a view already adopted (the kit's external id
exists) is left alone, so whichever module runs first does the work and the
other finds nothing to do.
"""
import logging

from odoo.tools.convert import convert_file

_logger = logging.getLogger(__name__)

KIT = 'bemade_portal_kit'
CLINIC = 'bemade_sports_clinic'

# Every view the kit adopted: (old module, old name, new name). One list for
# every phase (P3c1 here, P3c2 appends).
ADOPTED_VIEWS = (
    # Task 5369 (kit P3c1): the icons and the first components.
    (CLINIC, 'sc_icon', 'pk_icon'),
    (CLINIC, 'sc_frontend_layout', 'pk_frontend_layout'),
    (CLINIC, 'sc_status_chip', 'pk_status_chip'),
    (CLINIC, 'sc_stat_tile', 'pk_stat_tile'),
    (CLINIC, 'sc_card', 'pk_card'),
    (CLINIC, 'sc_section_header', 'pk_section_header'),
    (CLINIC, 'sc_list_add_cancel', 'pk_list_add_cancel'),
    (CLINIC, 'sc_edit_card_done', 'pk_edit_card_done'),
    (CLINIC, 'sc_empty_state', 'pk_empty_state'),
)

# The kit's data files that hold adopted views (loaded by load_kit_views).
KIT_VIEW_FILES = (
    'views/pk_layout.xml',
    'views/pk_components.xml',
)


def adopt_views(cr, mapping=ADOPTED_VIEWS):
    """Give each old view of ``mapping`` its kit external id and key.

    ``mapping``: ``(old_module, old_name, new_name)`` triples. Returns the
    ``(old xmlid, new xmlid, view id)`` triples adopted by this call.
    """
    adopted = []
    for old_module, old_name, new_name in mapping:
        old_xmlid = '%s.%s' % (old_module, old_name)
        new_xmlid = '%s.%s' % (KIT, new_name)
        cr.execute(
            "SELECT 1 FROM ir_model_data WHERE module = %s AND name = %s",
            (KIT, new_name),
        )
        if cr.fetchone():
            continue  # already adopted (or created by the kit)
        cr.execute(
            """UPDATE ir_model_data SET module = %s, name = %s
                WHERE module = %s AND name = %s AND model = 'ir.ui.view'
            RETURNING res_id""",
            (KIT, new_name, old_module, old_name),
        )
        row = cr.fetchone()
        if not row:
            continue  # nothing to adopt (e.g. the consumer is not installed)
        # Every view under the old key: the record and its website copies.
        cr.execute("UPDATE ir_ui_view SET key = %s WHERE key = %s", (new_xmlid, old_xmlid))
        adopted.append((old_xmlid, new_xmlid, row[0]))
        _logger.info("portal kit: view %s (id %s) adopted as %s", old_xmlid, row[0], new_xmlid)
    return adopted


def load_kit_views(env):
    """Load the kit's view files now (mode ``update``).

    For a consumer's pre-migration when the kit is not upgraded in the same
    run: the adopted views take the kit's arch and the kit's new views exist
    before the consumer's data refers to them. The kit's next upgrade loads
    the same files again (no-op).
    """
    if KIT in env.registry.updated_modules:
        return False
    for filename in KIT_VIEW_FILES:
        convert_file(env, KIT, filename, {}, mode='update', noupdate=False)
    _logger.info("portal kit: view files loaded from the consumer's migration (%s)", ', '.join(KIT_VIEW_FILES))
    return True
