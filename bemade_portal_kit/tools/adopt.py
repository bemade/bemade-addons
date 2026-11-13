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
* a database that has the consumer but not the kit (the consumer at a
  version older than the kit) installs the kit as a NEW dependency during
  the consumer's upgrade. A module being installed runs no migration
  script, so the kit's pre-migration does not run; its ``pre_init_hook``
  (``hooks.py``, task 5372) adopts the views instead, before the kit's data
  load. Without it the kit created new views and the consumer's
  pre-migration found the kit's external ids, took the views for adopted,
  and ``_process_end`` deleted the old ones;
* ``-u <consumer>`` alone does not upgrade the kit (an upgrade adds the
  dependents of a module, not its dependencies), so the consumer's own
  pre-migration must adopt the views too, or ``_process_end`` deletes them.
  When the kit was not upgraded in the same run, the consumer's
  pre-migration also loads the kit's view files (``load_kit_views``), so
  that the kit's new views (``pk_icon_extra``, which the consumer inherits)
  exist before the consumer's data refers to them.

So there are three entry points, each needed for one upgrade path: the
kit's install hook (kit newly installed), the kit's pre-migration
(19.0.1.5.0 and each later adoption's, kit upgraded) and the consumer's pre-migration (consumer
upgraded alone). A later adoption (``ADOPTED_VIEWS`` grows) must be reachable
from all three.

``adopt_views`` is idempotent: a view already adopted (the kit's external id
exists) is left alone, so whichever entry point runs first does the work and
the others find nothing to do. When the kit's external id AND the old one
both exist, nothing is changed either, but a WARNING names both: the kit
created its own view instead of adopting the old one, and the consumer's
upgrade is about to delete the old view (no automatic repair).
"""
import logging
import re

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
    # Task 5370 (kit P4b): the status pill select and the form guard's slots.
    (CLINIC, 'sc_status_pill_select', 'pk_status_pill_select'),
    (CLINIC, 'sc_form_guard_slots', 'pk_form_guard_slots'),
    # Task 5381 (kit P4c2): the edit card head, the display row, the sheet
    # and the page tabs.
    (CLINIC, 'sc_edit_card_head', 'pk_edit_card_head'),
    (CLINIC, 'sc_display_row', 'pk_display_row'),
    (CLINIC, 'sc_sheet', 'pk_sheet'),
    (CLINIC, 'sc_page_tabs', 'pk_page_tabs'),
    # Task 5382 (kit P4c3): the autosave field.
    (CLINIC, 'sc_field_autosave', 'pk_field_autosave'),
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
            "SELECT res_id FROM ir_model_data WHERE module = %s AND name = %s",
            (KIT, new_name),
        )
        kit_row = cr.fetchone()
        if kit_row:
            # Already adopted (or created by the kit). If the old external id
            # is still there too, the kit did not adopt it: say so.
            cr.execute(
                "SELECT res_id FROM ir_model_data WHERE module = %s AND name = %s AND model = 'ir.ui.view'",
                (old_module, old_name),
            )
            old_row = cr.fetchone()
            if old_row:
                _logger.warning(
                    "portal kit: view %s (id %s) not adopted: %s exists already (id %s);"
                    " the old view will be deleted with its translations and inheriting views",
                    old_xmlid, old_row[0], new_xmlid, kit_row[0],
                )
            continue
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


def strip_translated_attributes(cr, attributes):
    """Remove ``attributes`` (renamed, so dead) from the TRANSLATIONS of every
    view's ``arch_db``; returns the number of views changed.

    Task 5370 (P4b). A translated term may hold markup (``<span
    data-x-msg="k">…</span>``). When the source renames such an attribute,
    Odoo merges the source's attributes into the existing translation but
    never drops the translation's own: the old attribute stays, dead, next to
    the new one in every non-English value. The source (``en_US``) is never
    touched. Plain SQL, for a migration. Idempotent.
    """
    if not attributes:
        return 0
    pattern = r'\s(?:%s)="[^"]*"' % '|'.join(re.escape(name) for name in attributes)
    cr.execute(
        """UPDATE ir_ui_view v
              SET arch_db = (
                  SELECT jsonb_object_agg(e.key, CASE WHEN e.key = 'en_US' THEN e.value
                                                      ELSE regexp_replace(e.value, %(re)s, '', 'g') END)
                    FROM jsonb_each_text(v.arch_db) e)
            WHERE EXISTS (SELECT 1 FROM jsonb_each_text(v.arch_db) e
                           WHERE e.key != 'en_US' AND e.value ~ %(re)s)""",
        {'re': pattern},
    )
    if cr.rowcount:
        _logger.info("portal kit: renamed attributes %s removed from the translations of %s views",
                     ', '.join(attributes), cr.rowcount)
    return cr.rowcount
