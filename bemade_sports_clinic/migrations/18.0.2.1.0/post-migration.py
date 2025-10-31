# Copyright (C) FitCrew
# Odoo standard migration script executed on module upgrade for version 18.0.2.1.0
# Purpose: migrate legacy sports_event.team_id -> sports_event_team_rel(team_ids)

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    # 1) Populate M2M from legacy M2O if column exists
    try:
        cr.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'sports_event' AND column_name = 'team_id'
            """
        )
        has_legacy = bool(cr.fetchone())
    except Exception:
        has_legacy = False

    if has_legacy:
        # Insert missing M2M rows from legacy team_id
        # Avoid duplicates using NOT EXISTS
        cr.execute(
            """
            INSERT INTO sports_event_team_rel (event_id, team_id)
            SELECT e.id, e.team_id
            FROM sports_event e
            WHERE e.team_id IS NOT NULL
              AND NOT EXISTS (
                SELECT 1 FROM sports_event_team_rel r
                WHERE r.event_id = e.id AND r.team_id = e.team_id
              )
            """
        )

    # 2) Recompute partner_id from team_ids for all events
    try:
        env = api.Environment(cr, SUPERUSER_ID, {})
        Event = env['sports.event']
        events = Event.search([])
        # Call compute directly to ensure correctness regardless of store policies
        for ev in events:
            try:
                ev._compute_partner_id()
            except Exception:
                # Continue best-effort if any single record errors out
                pass
    except Exception:
        # Non-blocking
        pass
