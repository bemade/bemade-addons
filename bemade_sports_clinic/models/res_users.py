from odoo import models, fields, api, _, Command
from odoo.tools import format_datetime
from datetime import time, timedelta
import logging

import pytz

_logger = logging.getLogger(__name__)

# Morning-briefing config (global). The send time is the user-local clock time
# at/after which the day's digest is sent; the default-tz param is shared with
# slice C and used when a user (and their partner) has no tz on file.
DIGEST_MORNING_SEND_TIME_PARAM = "bemade_sports_clinic.digest_morning_send_time"
DIGEST_MORNING_SEND_TIME_DEFAULT = "07:00"
DIGEST_DEFAULT_TZ_PARAM = "bemade_sports_clinic.digest_default_timezone"
# A most-recent snapshot captured within this window of the send moment is "too
# close to send" to be a 24h baseline; the delta falls back to the prior one.
DIGEST_BASELINE_MIN_AGE = timedelta(hours=1)
# Roles that receive a per-team line, and how they scope role-visible activity.
DIGEST_COACH_ROLES = {"head_coach", "coach"}
DIGEST_TP_ROLES = {"head_therapist", "therapist", "doctor"}


class User(models.Model):
    _inherit = "res.users"

    accessible_team_ids = fields.Many2many(
        comodel_name="sports.team",
        compute="_compute_accessible_team_ids",
        inverse="_inverse_accessible_team_ids",
    )

    # Per-user morning-briefing preferences (task 1268, digest epic slice D).
    digest_daily_enabled = fields.Boolean(
        string="Daily Morning Briefing",
        default=True,
        help="Receive a daily PHI-free morning summary email for your teams "
        "(counts, 24h deltas and dashboard links — no medical data).",
    )
    digest_send_when_empty = fields.Boolean(
        string="Send Briefing Even When Empty",
        default=False,
        help="When off (default), the morning briefing is skipped on days with "
        "no changes across your teams. Turn on to always receive it.",
    )
    # Per-user-per-local-date idempotency guard for the morning-briefing cron.
    # Stores the last user-local date a briefing decision was made (sent OR
    # suppressed), so the hourly cron sends at most one briefing per local day.
    digest_last_sent_date = fields.Date(
        string="Morning Briefing Last Sent (local date)",
        copy=False,
        readonly=True,
    )

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + [
            "digest_daily_enabled",
            "digest_send_when_empty",
        ]

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + [
            "digest_daily_enabled",
            "digest_send_when_empty",
        ]

    def _compute_accessible_team_ids(self):
        for rec in self:
            rec.accessible_team_ids = rec.partner_id.teams_served_ids

    def _inverse_accessible_team_ids(self):
        for rec in self:
            removed_teams = rec.partner_id.teams_served_ids - rec.accessible_team_ids
            added_teams = rec.accessible_team_ids - rec.partner_id.teams_served_ids
            removed_teams = rec.partner_id.teams_served_ids.filtered(
                lambda team: team in removed_teams
            )
            removed_teams.remove_access(self)
            self.env["sports.team.staff"].create(
                [
                    {
                        "team_id": team.id,
                        "partner_id": rec.partner_id.id,
                        "role": "other",
                    }
                    for team in added_teams
                ]
            )
    
    def write(self, vals):
        """Override write to trigger treatment professional group assignment when portal access is granted."""
        # Process user updates for portal access changes

        # Archiving a user (portal-access revoke) must scrub the person from
        # follower lists and future event assignments, even though their
        # contact may legitimately stay active (task 399).
        archiving = 'active' in vals and not vals.get('active')

        # Check if groups_id is being modified (portal access being granted/revoked)
        if 'group_ids' in vals:
            # Get the portal group reference
            portal_group = self.env.ref('base.group_portal')
            
            # Store old group memberships before making changes
            old_groups_by_user = {user.id: user.group_ids.ids for user in self}
            # Store old group memberships for comparison
            
            # Apply the changes first
            result = super().write(vals)
            
            # Check each user to see if portal access was granted
            for user in self:
                old_groups = old_groups_by_user[user.id]
                new_groups = user.group_ids.ids
                # Check if portal access was granted
                
                if portal_group.id in new_groups and portal_group.id not in old_groups:
                    # Portal access was just granted - reconcile ALL portal groups
                    # (treatment professional *and* team coach) for this user.
                    staff_records = self.env['sports.team.staff'].search([
                        ('partner_id', '=', user.partner_id.id)
                    ])
                    if staff_records:
                        staff_records._update_all_portal_groups(user)

            if archiving:
                self.mapped('partner_id')._sports_clinic_purge_archived_staff()

            return result
        else:
            # No group changes, use normal write
            pass

        # If groups_id is not being modified, use normal write
        res = super().write(vals)
        if archiving:
            self.mapped('partner_id')._sports_clinic_purge_archived_staff()
        return res
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to trigger treatment professional group assignment when portal users are created."""
        # Process user creation for portal access
        
        # Create the users first
        users = super().create(vals_list)
        
        # Get the portal group reference
        portal_group = self.env.ref('base.group_portal')
        # Check for portal access in created users
        
        # Check each created user to see if they were created with portal access
        for user in users:
            # Check if user was created with portal access
            
            if portal_group.id in user.group_ids.ids:
                # User was created with portal access - reconcile ALL portal groups
                # (treatment professional *and* team coach) for this user.
                staff_records = self.env['sports.team.staff'].search([
                    ('partner_id', '=', user.partner_id.id)
                ])
                if staff_records:
                    staff_records._update_all_portal_groups(user)

        return users

    # ----------------------------------------------------------------------
    # Morning briefing (task 1268, digest epic slice D) — daily PHI-free email
    # ----------------------------------------------------------------------
    # An hourly cron sends ONE per-user, per-local-date "morning briefing" at
    # the configured user-local time. Law 25: the mail carries only per-team
    # counts, signed 24h deltas, team/event names and dashboard backlinks —
    # never a player name or any clinical/injury detail. Deltas are computed
    # against slice C's most recent stored snapshot stage counts.

    @api.model
    def _digest_morning_send_time(self):
        """Parsed (hour, minute) of the configured user-local send time."""
        raw = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(
                DIGEST_MORNING_SEND_TIME_PARAM, DIGEST_MORNING_SEND_TIME_DEFAULT
            )
        )
        try:
            hh, mm = str(raw).split(":")
            return time(int(hh), int(mm))
        except (ValueError, TypeError):
            return time(7, 0)

    def _digest_resolve_timezone(self):
        """Resolve a user's morning-briefing timezone: the user's own tz, else
        their partner's tz, else the global default-tz config param, else the
        company partner tz, else UTC. Always returns a pytz-valid name."""
        self.ensure_one()
        candidates = []
        if self.tz:
            candidates.append(self.tz)
        partner = self.partner_id
        if partner and partner.tz:
            candidates.append(partner.tz)
        param = (
            self.env["ir.config_parameter"].sudo().get_param(DIGEST_DEFAULT_TZ_PARAM)
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
    def _digest_delta_baseline(self, team, now):
        """Return the ``sports.team.digest`` snapshot to use as the 24h delta
        baseline for ``team``, or ``None`` if none is usable.

        Baseline = the team's most recent snapshot (from slice C, captured
        overnight). Fallback = the previous snapshot when the most recent is
        captured too close to the send moment to be a 24h baseline. No snapshot
        at all -> ``None`` (caller shows absolute counts, no delta)."""
        snaps = (
            self.env["sports.team.digest"]
            .sudo()
            .search(
                [("team_id", "=", team.id)],
                order="captured_at desc, id desc",
                limit=2,
            )
        )
        if not snaps:
            return None
        recent = snaps[0]
        if (
            len(snaps) > 1
            and recent.captured_at
            and (now - recent.captured_at) < DIGEST_BASELINE_MIN_AGE
        ):
            return snaps[1]
        return recent

    def _digest_pending_verify_count(self, team):
        """Open 'Verify injury' to-do activities on the team's injuries (the
        count only — the underlying activities are untouched)."""
        injuries = (
            self.env["sports.patient.injury"]
            .sudo()
            .search(
                [
                    "|",
                    ("team_id", "=", team.id),
                    ("patient_id.team_ids", "in", team.id),
                ]
            )
        )
        if not injuries:
            return 0
        return (
            self.env["mail.activity"]
            .sudo()
            .search_count(
                [
                    ("res_model", "=", "sports.patient.injury"),
                    ("res_id", "in", injuries.ids),
                    ("summary", "=", "Verify injury"),
                ]
            )
        )

    def _digest_build_team_line(self, staff, role, now, cutoff, base_url):
        """Build one PHI-free per-team summary dict for the recipient, scoped to
        their ``role`` on that team, or ``None`` if the team should be skipped."""
        team = staff.team_id.sudo()
        red = team.stage_no_play_count
        yellow = team.stage_practice_ok_count

        baseline = self._digest_delta_baseline(team, now)
        if baseline is not None:
            delta_red = red - baseline.stage_no_play_count
            delta_yellow = yellow - baseline.stage_practice_ok_count
            red_delta_str = " (%+d)" % delta_red
            yellow_delta_str = " (%+d)" % delta_yellow
        else:
            delta_red = delta_yellow = None
            red_delta_str = yellow_delta_str = ""

        patients = team.patient_ids
        inj_field = "dashboard_new_injury_count_%s" % role
        act_field = "dashboard_last_activity_%s" % role
        new_injuries = sum(patients.mapped(inj_field))
        changes = len(
            patients.filtered(
                lambda p: p[act_field] and p[act_field] >= cutoff
            )
        )
        pending_verify = self._digest_pending_verify_count(team)
        pending_removal = len(patients.filtered("pending_removal"))

        url = "%s/my/team?team_id=%s" % (base_url, team.id) if base_url else ""
        # Task 1270 (slice F): the full team announcement text rides in the
        # briefing, under the all-staff framing. This is an intentional,
        # author-written all-staff broadcast (NOT player PHI) — it carries its
        # own compose-time Law 25 warning.
        announcement = (team.announcement or "").strip()
        return {
            "id": team.id,
            "name": team.name,
            "url": url,
            "announcement": announcement or None,
            "announcement_is_expired": (
                bool(team.announcement_is_expired) if announcement else False
            ),
            "announcement_deadline": (
                fields.Date.to_string(team.announcement_deadline)
                if (announcement and team.announcement_deadline)
                else None
            ),
            "red": red,
            "yellow": yellow,
            "delta_red": delta_red,
            "delta_yellow": delta_yellow,
            "red_delta_str": red_delta_str,
            "yellow_delta_str": yellow_delta_str,
            "new_injuries": new_injuries,
            "changes": changes,
            "pending_verify": pending_verify,
            "pending_removal": pending_removal,
        }

    def _digest_build_for_user(self, now, cutoff, base_url):
        """Return ``(team_lines, events)`` for this user: role-scoped per-team
        summaries (most-active first) and the deduped 7d upcoming-event union.

        Only eligible staff lines are included: silent_notifications and
        archived/revoked access are dropped (``_is_follower_eligible``); the
        ``other`` role is skipped; doctors are scoped as TP."""
        self.ensure_one()
        partner = self.partner_id
        team_lines = []
        seen_events = self.env["sports.event"].sudo()
        events = []
        for staff in partner.sudo().team_staff_rel_ids:
            if not staff._is_follower_eligible():
                continue
            if staff.role in DIGEST_COACH_ROLES:
                role = "coach"
            elif staff.role in DIGEST_TP_ROLES:
                role = "tp"
            else:  # 'other' -> skip
                continue
            line = self._digest_build_team_line(staff, role, now, cutoff, base_url)
            if line is not None:
                team_lines.append(line)
            for ev in staff.team_id.sudo().dashboard_upcoming_event_ids:
                if ev not in seen_events:
                    seen_events |= ev
                    events.append(ev)
        team_lines.sort(key=lambda l: (-l["changes"], l["name"] or ""))
        events.sort(key=lambda e: e.date_start or fields.Datetime.now())
        tz_name = self._digest_resolve_timezone()
        ev_lang = self.partner_id.lang or self.lang or self.env.lang
        event_data = []
        for ev in events:
            date_label = ""
            if ev.date_start:
                date_label = format_datetime(
                    self.env, ev.date_start, tz=tz_name,
                    dt_format="EEE d MMM, HH 'h' mm", lang_code=ev_lang,
                )
            event_data.append({
                "name": ev.name,
                "date_start": ev.date_start,
                "date_label": date_label,
            })
        return team_lines, event_data

    @api.model
    def _digest_line_has_content(self, line):
        """A team line is 'new activity' when it carries any change signal —
        deltas, new injuries, role-scoped changes, or pending to-do counts. The
        red/yellow standing alone (unchanged) is not new activity."""
        return bool(
            line["new_injuries"]
            or line["changes"]
            or line["pending_verify"]
            or line["pending_removal"]
            or (line["delta_red"] not in (None, 0))
            or (line["delta_yellow"] not in (None, 0))
        )

    def _digest_has_content(self, team_lines, events):
        return bool(events) or any(
            self._digest_line_has_content(line) for line in team_lines
        )

    def _digest_fallback_body(self, team_lines, events):
        """PHI-free bilingual HTML body used when the mail template is missing
        or fails to render. Counts + deltas + team/event names + links only —
        never a player name or clinical detail."""
        from markupsafe import Markup, escape

        parts = [
            Markup("<p>%s</p>")
            % escape(
                _(
                    "Your daily team briefing / Votre sommaire quotidien d'équipe:"
                )
            )
        ]
        for team in team_lines:
            lines = [Markup("<p><strong>%s</strong></p>") % escape(team["name"])]
            # Task 1380: the announcement sits directly under the team name,
            # before the counts block.
            if team.get("announcement"):
                expired_suffix = (
                    " " + _("(expired / expirée)")
                    if team.get("announcement_is_expired")
                    else ""
                )
                lines.append(
                    Markup("<p><strong>%s%s</strong></p>")
                    % (
                        escape(_("Team announcement / Annonce de l'équipe:")),
                        escape(expired_suffix),
                    )
                )
                lines.append(
                    Markup('<p style="white-space:pre-wrap;">%s</p>')
                    % escape(team["announcement"])
                )
            items = [
                escape(
                    _(
                        "%(red)s no-play%(red_delta)s · %(yellow)s limited%(yellow_delta)s",
                        red=team["red"],
                        red_delta=team["red_delta_str"],
                        yellow=team["yellow"],
                        yellow_delta=team["yellow_delta_str"],
                    )
                )
            ]
            if team["new_injuries"]:
                items.append(
                    escape(_("%s new injury/injuries (24h)", team["new_injuries"]))
                )
            if team["changes"]:
                items.append(
                    escape(_("%s player(s) with changes (24h)", team["changes"]))
                )
            if team["pending_verify"]:
                items.append(
                    escape(
                        _(
                            "%s injury verification(s) pending",
                            team["pending_verify"],
                        )
                    )
                )
            if team["pending_removal"]:
                items.append(
                    escape(
                        _("%s player removal request(s)", team["pending_removal"])
                    )
                )
            lines.append(
                Markup("<ul>%s</ul>")
                % Markup("").join(Markup("<li>%s</li>") % it for it in items)
            )
            if team["url"]:
                lines.append(
                    Markup('<p><a href="%s">%s</a></p>')
                    % (
                        team["url"],
                        escape(_("Team dashboard / Tableau de bord")),
                    )
                )
            parts.append(Markup("").join(lines))
        if events:
            ev_lines = [
                Markup("<p><strong>%s</strong></p>")
                % escape(_("Upcoming events (7d) / Événements à venir (7 j):"))
            ]
            ev_items = []
            for ev in events:
                when = ev.get("date_label") or (
                    fields.Datetime.to_string(ev["date_start"])
                    if ev["date_start"]
                    else ""
                )
                ev_items.append(
                    escape(
                        _(
                            "%(name)s %(when)s",
                            name=ev["name"] or "",
                            when=when,
                        )
                    )
                )
            ev_lines.append(
                Markup("<ul>%s</ul>")
                % Markup("").join(Markup("<li>%s</li>") % it for it in ev_items)
            )
            ev_lines.append(
                Markup("<p>%s</p>")
                % escape(
                    _(
                        "Events not listed are outside our coverage plan — please "
                        "advise us. / Les événements non listés sont hors de notre "
                        "plan de couverture, avisez-nous."
                    )
                )
            )
            parts.append(Markup("").join(ev_lines))
        parts.append(
            Markup('<p style="color:#888;font-size:12px;">%s</p>')
            % escape(
                _(
                    "No medical data is included. / Aucune donnée médicale n'est "
                    "incluse."
                )
            )
        )
        return Markup("").join(parts)

    def _digest_send_one(self, team_lines, events, lang, template):
        """Render and deliver the morning briefing to this user's partner."""
        self.ensure_one()
        partner = self.partner_id
        body = None
        if template:
            try:
                tmpl = template.sudo().with_context(
                    lang=lang,
                    digest_teams=team_lines,
                    digest_events=events,
                )
                body = tmpl._render_field("body_html", partner.ids).get(partner.id)
            except Exception:  # pragma: no cover - render guard
                _logger.exception(
                    "Morning-briefing body render failed for partner %s",
                    partner.id,
                )
                body = None
        if not body:
            body = self.with_context(lang=lang)._digest_fallback_body(
                team_lines, events
            )
        subject = self.with_context(lang=lang).env._(
            "FitCrew — daily briefing / sommaire quotidien"
        )
        try:
            self.env["mail.thread"].sudo().with_context(lang=lang).message_notify(
                partner_ids=partner.ids,
                subject=subject,
                body=body,
                email_layout_xmlid="mail.mail_notification_light",
            )
        except Exception:  # pragma: no cover - never break the cron txn
            _logger.exception(
                "Morning-briefing send failed for partner %s", partner.id
            )

    @api.model
    def _digest_eligible_users(self):
        """Active users who are sports-clinic staff in a coach/TP role."""
        staff = (
            self.env["sports.team.staff"]
            .sudo()
            .search([("role", "in", list(DIGEST_COACH_ROLES | DIGEST_TP_ROLES))])
        )
        partners = staff.partner_id
        if not partners:
            return self.browse()
        return self.sudo().search(
            [("partner_id", "in", partners.ids), ("active", "=", True)]
        )

    @api.model
    def _cron_send_morning_digests(self, now=None):
        """Hourly cron entrypoint. For each eligible user, once their local
        clock has passed the configured send time for a local date AND no
        briefing decision has yet been made for that date, build their PHI-free
        briefing and send it (or suppress it when empty and the user has not
        opted into empty briefings). The per-user-per-local-date guard makes it
        idempotent and DST-safe; a missed hour self-heals on the next run.

        ``now`` is injectable so tests can pin a deterministic upper bound."""
        if now is None:
            now = fields.Datetime.now()
        send_time = self._digest_morning_send_time()
        cutoff = self.env["sports.patient"]._dashboard_window_cutoff()
        base_url = (
            self.env["ir.config_parameter"].sudo().get_param("web.base.url") or ""
        )
        template = self.env.ref(
            "bemade_sports_clinic.mail_template_morning_digest",
            raise_if_not_found=False,
        )
        default_lang = self.env.lang or "en_US"
        for user in self._digest_eligible_users():
            if not user.digest_daily_enabled:
                continue
            tz_name = user._digest_resolve_timezone()
            try:
                tz = pytz.timezone(tz_name)
            except Exception:  # pragma: no cover - _resolve guards this
                tz = pytz.UTC
            local_now = pytz.utc.localize(now).astimezone(tz)
            if local_now.time() < send_time:
                continue
            local_date = local_now.date()
            if user.digest_last_sent_date == local_date:
                continue
            try:
                team_lines, events = user._digest_build_for_user(
                    now, cutoff, base_url
                )
                if not team_lines and not events:
                    # No eligible teams at all -> nothing to say, and don't burn
                    # the guard (the user may gain a team later today).
                    continue
                has_content = user._digest_has_content(team_lines, events)
                if has_content or user.digest_send_when_empty:
                    lang = user.partner_id.lang or user.lang or default_lang
                    user._digest_send_one(team_lines, events, lang, template)
                # Record the daily decision (sent OR suppressed-empty) so the
                # briefing fires at most once per user per local date.
                user.sudo().write({"digest_last_sent_date": local_date})
            except Exception:  # pragma: no cover - one bad user must not stop others
                _logger.exception(
                    "Morning-briefing failed for user %s", user.id
                )
        return True
