import logging

from .models.sc_app_pwa import sc_fill_pwa_branding

_logger = logging.getLogger(__name__)

# Task 1541: the kit's switch (bemade_portal_kit.models.portal_kit.PK_SHELL_PARAM).
SC_KIT_SWITCH = 'bemade_portal_kit.enabled'
_TRUTHY = ('1', 'true', 'yes', 'on')


def sc_ensure_kit_enabled(env):
    """Task 1541 (19.0.2.0.0): the clinic portal is the app only, so the kit's
    switch (its home, « More », settings pages) must be on. Sets
    ``bemade_portal_kit.enabled`` to True when it is missing or falsy, and
    logs it; a truthy value is left as it is. Returns True when it wrote."""
    params = env['ir.config_parameter'].sudo()
    raw = params.get_param(SC_KIT_SWITCH)
    if str(raw or '').strip().lower() in _TRUTHY:
        return False
    params.set_param(SC_KIT_SWITCH, 'True')
    _logger.info("bemade_sports_clinic: %s was %r, set to True (the clinic portal is the app only)",
                 SC_KIT_SWITCH, raw)
    return True


def post_init_hook(env):
    """Migrate legacy team_id to team_ids on sports.event and recompute partner_id.

    - For any event having a non-null team_id column (from previous versions),
      set team_ids to that single team.
    - Recompute partner_id based on team_ids.
    - Task 5201 (kit P6): the company's installable app fields get the Fit
      Crew name, colours and icons where they are empty.
    """
    sc_fill_pwa_branding(env)
    cr = env.cr
    Event = env['sports.event']

    # Best-effort: detect if legacy column exists; if not, skip silently
    has_legacy = False
    try:
        cr.execute("""
            SELECT 1
            FROM information_schema.columns 
            WHERE table_name = 'sports_event' AND column_name = 'team_id'
        """)
        has_legacy = bool(cr.fetchone())
    except Exception:
        has_legacy = False

    if has_legacy:
        # Find events where team_ids is empty but legacy team_id is set
        # Use SQL to avoid M2M join costs, then set via ORM
        cr.execute("""
            SELECT e.id, e.team_id
            FROM sports_event e
            WHERE e.team_id IS NOT NULL
        """)
        rows = cr.fetchall() or []
        if rows:
            event_map = {}
            for ev_id, team_id in rows:
                if ev_id and team_id:
                    event_map.setdefault(ev_id, team_id)
            # Apply in batches
            BATCH = 500
            ev_ids = list(event_map.keys())
            for i in range(0, len(ev_ids), BATCH):
                chunk = ev_ids[i:i+BATCH]
                events = Event.browse(chunk)
                # Build full list for this chunk
                vals_list = []
                for ev in events:
                    t_id = event_map.get(ev.id)
                    if t_id:
                        vals_list.append((ev, [(6, 0, [t_id])]))
                # Write team_ids
                for ev, cmd in vals_list:
                    try:
                        ev.write({'team_ids': cmd})
                    except Exception:
                        # Do not block migration on edge cases
                        pass

    # Recompute partner_id for all events
    try:
        all_events = Event.search([])
        # Trigger compute by writing no-op on relevant dependency
        # Safer: call helper if present
        if hasattr(Event, 'action_recompute_partner_ids'):
            Event.action_recompute_partner_ids()
        else:
            # Fallback: touch records to recompute stored compute
            for ev in all_events:
                ev._compute_partner_id()
    except Exception:
        # Non-blocking
        pass
