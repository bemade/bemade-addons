from odoo import api, fields, models, _
from datetime import datetime, timedelta, time
import logging

import pytz

_logger = logging.getLogger(__name__)

# Config params (global). The capture time is the team-local clock time at/after
# which the day's snapshot is taken; the default timezone is the fallback used
# when a team's organization partner has no tz on file.
DIGEST_CAPTURE_TIME_PARAM = "bemade_sports_clinic.digest_capture_time"
DIGEST_CAPTURE_TIME_DEFAULT = "00:00"
DIGEST_DEFAULT_TZ_PARAM = "bemade_sports_clinic.digest_default_timezone"
# Per-team retention default (days). A team may override via digest_retention_days.
DIGEST_RETENTION_DAYS_DEFAULT = 365


class SportsTeamDigest(models.Model):
    """A stored, once-per-local-day snapshot of a team dashboard's trailing-24h
    change feed (task 1267, digest epic slice C).

    It does NOT re-derive change detection: at capture it calls the SAME
    per-player builders that drive the live dashboard
    (``sports.patient._dashboard_change_items`` / ``_dashboard_change_synopsis``)
    for BOTH the coach (external) and TP (internal+external) scope, and freezes
    the result as STRUCTURED data (``item_data``, JSON) tagged by visibility.

    Law 25: the snapshot is never frozen HTML. Every historical view re-gates the
    stored structured items by the viewer's role (``_render_for_role``): a coach
    view can no more surface an internal note or a hidden-from-coaches injury than
    the live coach dashboard can — the internal-tagged items are dropped at read.
    """

    _name = "sports.team.digest"
    _description = "Team Dashboard Daily Digest Snapshot"
    _order = "snapshot_date desc, team_id"

    team_id = fields.Many2one(
        comodel_name="sports.team",
        string="Team",
        required=True,
        ondelete="cascade",
        index=True,
    )
    snapshot_date = fields.Date(
        string="Snapshot Date",
        required=True,
        index=True,
        help="The team-local date this snapshot represents (captured at/after the "
        "configured local capture time).",
    )
    captured_at = fields.Datetime(
        string="Captured At (UTC)",
        required=True,
        help="The exact UTC moment the snapshot was taken. The change window is "
        "the 24h ending here.",
    )
    timezone = fields.Char(
        string="Resolved Timezone",
        help="The timezone actually used to resolve the local capture date — "
        "recorded for audit / DST clarity.",
    )
    name = fields.Char(compute="_compute_name", store=True)

    # Structured change feed, tagged by visibility. See _capture_team for shape.
    item_data = fields.Json(string="Change Items")
    synopsis = fields.Text(
        string="Synopsis",
        help="Short team-level summary of the captured day (audit convenience).",
    )

    # Cached aggregate counts over the captured window (TP superset).
    change_count = fields.Integer(string="Changes")
    new_injury_count = fields.Integer(string="New Injuries")
    note_update_count = fields.Integer(string="Note Updates")
    player_count = fields.Integer(string="Players With Changes")

    # Team stage counts at capture time — slice D (#1268) reads the most recent
    # snapshot's stored counts to compute its morning "+/- vs 24h" deltas on the
    # red/yellow/green header. Storing them here is what makes that delta possible.
    stage_no_play_count = fields.Integer(string="No Play")
    stage_practice_ok_count = fields.Integer(string="Practice OK")
    stage_healthy_count = fields.Integer(string="Healthy")

    digest_html = fields.Html(
        string="Digest",
        compute="_compute_digest_html",
        sanitize=False,
        help="Rendered TP-scoped view of the stored snapshot (backend form).",
    )

    _unique_team_date = models.Constraint(
        "unique(team_id, snapshot_date)",
        "A team can only have one digest snapshot per local date.",
    )

    # ------------------------------------------------------------------ compute
    @api.depends("team_id", "snapshot_date")
    def _compute_name(self):
        for rec in self:
            team_name = rec.team_id.sudo().name or _("Team")
            rec.name = "%s — %s" % (team_name, rec.snapshot_date or "")

    def _compute_digest_html(self):
        """Render the TP-scoped view for the backend form. Non-stored: re-gated
        from the structured item_data on every read (never frozen HTML)."""
        for rec in self:
            players = rec._render_for_role("tp")
            rec.digest_html = self.env["ir.qweb"]._render(
                "bemade_sports_clinic.team_digest_render",
                {
                    "players": players,
                    "announcement": (rec.item_data or {}).get("announcement"),
                    # Task 1385 (CR-A #2): backend form → injury names link to the
                    # backend record form, not the portal edit route.
                    "backend_link": True,
                },
            )

    # -------------------------------------------------------- role re-gate (read)
    def _render_for_role(self, role):
        """Return the role-appropriate, render-ready per-player structures from
        the stored ``item_data``.

        ``role`` in ``('coach', 'tp')`` is the Law-25 gate applied AT READ:
          - ``tp``  -> every stored item (internal + external);
          - ``coach`` -> internal-tagged items are dropped, and any internal
            sub-item (e.g. an internal note nested in a new-injury unit) is
            stripped from the items that remain.
        The stored visibility tags come straight from the coach builder's own
        output at capture, so this filter mirrors the live coach dashboard exactly
        rather than re-implementing the visibility rules.
        """
        self.ensure_one()
        if role not in ("coach", "tp"):
            return []
        data = self.item_data or {}
        result = []
        for player in data.get("players", []):
            items = player.get("items", []) or []
            if role == "coach":
                kept = []
                for it in items:
                    if it.get("visibility") == "internal":
                        continue
                    it = dict(it)
                    subs = it.get("sub_items")
                    if subs:
                        it["sub_items"] = [
                            s for s in subs if s.get("visibility") != "internal"
                        ]
                    kept.append(it)
                items = kept
            # Task 1385: active-injury detail for the static section, role-gated
            # (coach drops hidden-from-coaches injuries — tagged "internal" at
            # capture). Historical snapshots that predate 1385 simply have no
            # active_injuries key (forward-only) -> empty static section.
            active_injuries = player.get("active_injuries", []) or []
            if role == "coach":
                active_injuries = [
                    a for a in active_injuries if a.get("visibility") != "internal"
                ]
                # Task 1385 (CR-D2): the stored snapshot is the TP superset, so a
                # non-hidden injury still carries its internal_notes. Strip them
                # from the coach read — coaches see external notes only.
                active_injuries = [
                    {**a, "internal_notes": ""} for a in active_injuries
                ]
            # Task 1385: apply the same injury de-dup as the live card — only the
            # detail-field change items (category "injury") of an injury shown in
            # the static section are dropped (they are marked up top). Notes,
            # new-injury units, player-level and non-shown-injury changes stay.
            shown_injury_ids = {
                a.get("injury_id") for a in active_injuries if a.get("injury_id")
            }
            deduped = [
                it for it in items
                if not (
                    it.get("category") == "injury"
                    and it.get("injury_id")
                    and it.get("injury_id") in shown_injury_ids
                )
            ]
            # Keep rendering a player who has either a change feed OR standing
            # active injuries / card fields to show.
            if not deduped and not active_injuries and not player.get("predicted_return_date") and not player.get("training_recommendation"):
                continue
            synopsis = (player.get("synopsis") or {}).get(role) or []
            result.append(
                {
                    "player_id": player.get("player_id"),
                    "player_name": player.get("player_name"),
                    "position": player.get("position"),
                    "predicted_return_date": player.get("predicted_return_date", ""),
                    "training_recommendation": player.get("training_recommendation", ""),
                    "last_consultation_date": player.get("last_consultation_date", ""),
                    "active_injuries": active_injuries,
                    "changed_recently": bool(player.get("changed_recently")),
                    "items": deduped,
                    "synopsis": synopsis,
                }
            )
        return result

    # --------------------------------------------------------- capture (write)
    @api.model
    def _digest_item_key(self, item):
        """Identity of a change-item, stable across the coach/TP builds so a TP
        (superset) item can be tagged coach-visible iff the coach build emitted
        the equivalent item."""
        injury = item.get("injury")
        injury_id = injury.id if injury else False
        return (item.get("category"), item.get("field"), injury_id)

    def _serialize_item(self, item, coach_keys):
        """JSON-safe copy of one live change-item dict, tagged with a visibility
        derived from the coach build (never a recordset — snapshots outlive the
        records they summarize)."""
        injury = item.get("injury")
        visibility = "external" if self._digest_item_key(item) in coach_keys else "internal"
        data = {
            "category": item.get("category"),
            "field": item.get("field"),
            "label": item.get("label"),
            "value": item.get("value"),
            # Task 1385 (CR-A #4): freeze the pre-window value so the snapshot
            # render shows the same "ancienne → nouvelle" delta as the live feed.
            "old_value": item.get("old_value") or "",
            "preview": item.get("preview"),
            "is_long": bool(item.get("is_long")),
            "icon": item.get("icon"),
            "injury_diagnosis": (injury.diagnosis if injury else False) or False,
            # Task 1385: carry the injury id so the snapshot render can apply the
            # same injury de-dup as the live card (drop a change already shown in
            # the static active-injury section). Correlation only, within this
            # frozen snapshot.
            "injury_id": injury.id if injury else False,
            "visibility": visibility,
        }
        subs = item.get("sub_items")
        if subs:
            data["sub_items"] = [self._serialize_item(s, coach_keys) for s in subs]
        return data

    @api.model
    def _coach_visible_keys(self, coach_items):
        keys = set()
        for it in coach_items:
            keys.add(self._digest_item_key(it))
            for sub in it.get("sub_items", []) or []:
                keys.add(self._digest_item_key(sub))
        return keys

    @api.model
    def _announcement_snapshot(self, team):
        """JSON-safe freeze of a team's current announcement (task 1270), or
        ``None`` when there is no announcement."""
        body = (team.announcement or "").strip()
        if not body:
            return None
        return {
            "body": body,
            "deadline": (
                fields.Date.to_string(team.announcement_deadline)
                if team.announcement_deadline
                else None
            ),
            "is_expired": bool(team.announcement_is_expired),
            "author": team.announcement_author_id.name or "",
        }

    def _capture_team(self, team, captured_at, snapshot_date, timezone_name):
        """Create (or skip, if already present) the snapshot for one team/date.

        Reuses the live per-player builders for BOTH scopes; the TP build is the
        stored superset, the coach build supplies the visibility tags. Idempotent
        under the unique(team_id, snapshot_date) constraint.
        """
        Digest = self.sudo()
        existing = Digest.search(
            [("team_id", "=", team.id), ("snapshot_date", "=", snapshot_date)],
            limit=1,
        )
        if existing:
            return existing

        cutoff = captured_at - timedelta(
            hours=self.env["sports.patient"]._dashboard_window_hours()
        )
        show_position = bool(team.show_position_on_dashboard)

        # Frozen text (item labels + synopsis) is captured ONCE, so build it in the
        # clinic's language (the company language). Otherwise it inherits whatever
        # language the cron happens to run under and displays that on the French
        # portal regardless of the viewer (#1267 UAT: English leaked into the FR portal).
        lang = self.env.company.partner_id.lang or self.env.lang or "en_US"

        players = []
        change_count = new_injury_count = note_update_count = 0
        for patient in team.sudo().patient_ids:
            patient = patient.with_context(lang=lang)
            tp_items = patient._dashboard_change_items("tp", cutoff)
            # Task 1385: freeze the homogenized-card fields so the snapshot render
            # matches the live card — always-on predicted-return + training-rec,
            # the static active-injury detail (TP superset; each entry tagged with
            # its visibility so the coach read drops hidden injuries), last
            # consultation, and per-injury change-presence markers.
            changed_injuries = self.env["sports.patient"]._dashboard_injury_presence(
                patient, "tp", cutoff
            )
            active_injuries = []
            for inj in patient.injury_ids.filtered(lambda i: i.stage == "active"):
                detail = patient._card_injury_detail(inj, cutoff)
                detail["changed"] = inj.id in changed_injuries
                detail["visibility"] = (
                    "internal" if inj.hidden_from_coaches else "external"
                )
                active_injuries.append(detail)
            # Task 1385 (CR-A #5): a new injury is a static "Nouvelle" flag now,
            # not a feed row — so a player whose only activity is a freshly
            # reported injury still belongs in the digest even with no tp_items.
            has_new_injury = any(a.get("is_new") for a in active_injuries)
            if not tp_items and not has_new_injury:
                continue
            coach_items = patient._dashboard_change_items("coach", cutoff)
            coach_keys = self._coach_visible_keys(coach_items)
            serialized = [self._serialize_item(it, coach_keys) for it in tp_items]
            players.append(
                {
                    "player_id": patient.id,
                    "player_name": patient.name,
                    "position": (patient.position or "") if show_position else "",
                    "predicted_return_date": (
                        fields.Date.to_string(patient.predicted_return_date)
                        if patient.predicted_return_date else ""
                    ),
                    "training_recommendation": patient.training_recommendation or "",
                    "last_consultation_date": (
                        fields.Date.to_string(patient.last_consultation_date)
                        if patient.last_consultation_date else ""
                    ),
                    "active_injuries": active_injuries,
                    "changed_recently": bool(tp_items or has_new_injury),
                    "items": serialized,
                    "synopsis": {
                        "coach": patient._dashboard_change_synopsis(
                            "coach", items=coach_items
                        ),
                        "tp": patient._dashboard_change_synopsis(
                            "tp", items=tp_items
                        ),
                    },
                }
            )
            change_count += len(tp_items)
            # Task 1385 (CR-A #5): new injuries no longer appear as feed units,
            # so count them from the static active-injury flags instead.
            new_injury_count += sum(
                1 for a in active_injuries if a.get("is_new")
            )
            note_update_count += sum(
                1 for it in tp_items if it.get("category") == "note"
            )

        item_data = {
            "window_hours": self.env["sports.patient"]._dashboard_window_hours(),
            "players": players,
            # Task 1270 (slice F): freeze the current team announcement into the
            # snapshot so the historical view shows what was standing that day.
            # All-staff content (not PHI), so it is NOT role-gated at read.
            "announcement": self._announcement_snapshot(team),
        }
        synopsis = _(
            "%(players)s player(s) with changes · %(new)s new injury/injuries · "
            "%(notes)s note update(s)",
            players=len(players),
            new=new_injury_count,
            notes=note_update_count,
        )
        return Digest.create(
            {
                "team_id": team.id,
                "snapshot_date": snapshot_date,
                "captured_at": captured_at,
                "timezone": timezone_name,
                "item_data": item_data,
                "synopsis": synopsis,
                "change_count": change_count,
                "new_injury_count": new_injury_count,
                "note_update_count": note_update_count,
                "player_count": len(players),
                "stage_no_play_count": team.stage_no_play_count,
                "stage_practice_ok_count": team.stage_practice_ok_count,
                "stage_healthy_count": team.stage_healthy_count,
            }
        )

    # --------------------------------------------------------- timezone / config
    @api.model
    def _resolve_timezone(self, team):
        """Resolve a team's capture timezone: the team's organization partner
        address tz, else the global default-tz config param, else the company
        partner tz, else UTC. Always returns a pytz-valid name."""
        candidates = []
        partner = team.sudo().parent_id
        if partner and partner.tz:
            candidates.append(partner.tz)
        param = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(DIGEST_DEFAULT_TZ_PARAM)
        )
        if param:
            candidates.append(param)
        company_partner = self.env.company.partner_id
        if company_partner and company_partner.tz:
            candidates.append(company_partner.tz)
        for name in candidates:
            try:
                pytz.timezone(name)
                return name
            except Exception:  # pragma: no cover - defensive against bad config
                continue
        return "UTC"

    @api.model
    def _digest_capture_time(self):
        """Parsed (hour, minute) of the configured local capture time."""
        raw = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(DIGEST_CAPTURE_TIME_PARAM, DIGEST_CAPTURE_TIME_DEFAULT)
        )
        try:
            hh, mm = str(raw).split(":")
            return time(int(hh), int(mm))
        except (ValueError, TypeError):
            return time(0, 0)

    # -------------------------------------------------------------------- crons
    @api.model
    def _cron_capture_team_digests(self):
        """Hourly. Per team, resolve local time; once the local clock has passed
        the configured capture time for a local date AND no snapshot exists for
        that date, capture it. Hourly + per-local-date guard makes this
        DST-safe and resilient to downtime."""
        now_utc = fields.Datetime.now()
        capture_time = self._digest_capture_time()
        teams = self.env["sports.team"].sudo().search([])
        for team in teams:
            tz_name = self._resolve_timezone(team)
            try:
                tz = pytz.timezone(tz_name)
            except Exception:  # pragma: no cover - _resolve_timezone guards this
                tz = pytz.UTC
            local_now = pytz.utc.localize(now_utc).astimezone(tz)
            # The snapshot's local date is today (local) once we've passed the
            # capture time, else yesterday (server was down at the boundary).
            if local_now.time() >= capture_time:
                snapshot_date = local_now.date()
            else:
                snapshot_date = local_now.date() - timedelta(days=1)
            try:
                self._capture_team(team, now_utc, snapshot_date, tz_name)
            except Exception:  # pragma: no cover - one bad team must not stop others
                _logger.exception(
                    "Team digest capture failed for team %s", team.id
                )
        return True

    @api.model
    def _cron_purge_team_digests(self):
        """Daily. Drop snapshots older than each team's retention window."""
        today = fields.Date.today()
        teams = self.env["sports.team"].sudo().search([])
        for team in teams:
            # The field carries its own default (DIGEST_RETENTION_DAYS_DEFAULT);
            # read it directly — a stored 0 is an explicit "keep indefinitely",
            # NOT an unset that should fall back to the default.
            retention = team.digest_retention_days
            if not retention or retention <= 0:
                continue
            cutoff_date = today - timedelta(days=retention)
            stale = self.sudo().search(
                [
                    ("team_id", "=", team.id),
                    ("snapshot_date", "<", cutoff_date),
                ]
            )
            if stale:
                stale.unlink()
        return True
