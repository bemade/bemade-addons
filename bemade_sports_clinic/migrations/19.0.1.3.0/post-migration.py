"""Seed sports.injury.note.history from the live injury note fields (task 1241).

The module is already deployed, so the initial audit rows are created here
rather than in a post_init_hook: for every injury with a non-empty
internal_notes (resp. external_notes), create one history row with that
scope, authored by the superuser and dated with the injury's write_date.
Live field contents are left untouched.

Idempotent: an injury+scope pair that already has history rows is skipped,
so re-running the migration (or running it after some rows were captured
organically) never duplicates entries.
"""
import logging

_logger = logging.getLogger(__name__)

_NOTE_FIELDS = (
    ("internal_notes", "internal"),
    ("external_notes", "external"),
)


def migrate(cr, version):
    if not version:
        # Fresh install — capture hooks handle everything from the start.
        return

    from odoo.api import Environment, SUPERUSER_ID  # noqa: PLC0415

    env = Environment(cr, SUPERUSER_ID, {})
    History = env["sports.injury.note.history"]
    injuries = env["sports.patient.injury"].with_context(active_test=False).search([])

    existing_pairs = {
        (hist.injury_id.id, hist.scope)
        for hist in History.search([("injury_id", "in", injuries.ids)])
    }

    vals_list = []
    for injury in injuries:
        for fname, scope in _NOTE_FIELDS:
            content = injury[fname]
            if not (content and content.strip()):
                continue
            if (injury.id, scope) in existing_pairs:
                continue
            vals_list.append({
                "injury_id": injury.id,
                "scope": scope,
                "content": content,
                "author_id": SUPERUSER_ID,
                "note_datetime": injury.write_date,
            })

    if vals_list:
        History.create(vals_list)
        _logger.info(
            "Seeded %s injury note history row(s) from existing notes", len(vals_list)
        )
