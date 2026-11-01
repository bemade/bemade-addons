"""Task 1600 — close the stuck removal requests of players with no team.

A player whose last team was removed outside the official removal path kept
``pending_removal = True`` and an open « Player Removal Request » activity
that no one can action any more. Predicate (never ids — this repository is
public): ``pending_removal = True`` and no team, active or archived. Each such
player gets the flag cleared, and their open removal-request activities are
marked done with « Closed: the player is no longer on the team. » (in the
assignee's language). Idempotent; logs the counts.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    players, closed = env['sports.patient']._sc_clear_stale_removal_flags()
    _logger.info(
        "Task 1600: cleared pending_removal on %s player(s) with no team; "
        "closed %s open removal request(s).", len(players), closed)
