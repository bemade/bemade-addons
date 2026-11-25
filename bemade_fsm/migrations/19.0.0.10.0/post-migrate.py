"""Start the site note history from the current notes (durpro task 1727).

One ``fsm.site.note.history`` row per site that already has a note, dated at
the partner's last write and credited to the last known writer of the note
(else OdooBot), so the history begins with the text in use today.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    count = env["fsm.site.note.history"]._seed_from_current_notes()
    _logger.info("bemade_fsm: seeded %s site note history row(s)", count)
