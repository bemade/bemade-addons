# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError

WEEKDAYS = "1234567"
DEFAULT_TZ = "America/Toronto"
DEFAULT_VOLUME = {"quests": 3, "sessions_min": 3, "sessions_max": 5, "minutes": 0}  # where a ramp starts (quests: not ramped)
MIN_MINUTES_QUEST = 5  # during a ramp, the practice-time quest appears from this many minutes
GAP_CAP_SECONDS = 60  # practice time: an answer counts at most this long since the previous one


class Student(models.Model):
    _inherit = "homeschool.student"

    practice_handedness = fields.Selection(
        [("right", "Right-handed"), ("left", "Left-handed")], default="right", required=True,
        help="The lesson screen puts the keypad and the choices on this side.")
    practice_weekdays = fields.Char(
        default="12345", help="Practice days (ISO weekdays, 1 = Monday): quests are drawn on these days only.")
    practice_quests_per_day = fields.Integer(
        default=3, help="How many quests the day draws (the practice-time quest is one of them).")
    practice_sessions_min = fields.Integer(
        "Sessions a day (min)", default=3, help="The day's session quests ask for this many sessions at least.")
    practice_sessions_max = fields.Integer(
        "Sessions a day (max)", default=5, help="… and at most this many (drawn in the range, varied).")
    practice_minutes_goal = fields.Integer(
        "Practice-time quest (min)", default=0,
        help="Minutes of practice the day asks for (a quest of its own); 0: no practice-time quest. "
             "The learner sees the day's minutes on that quest only, never inside a session.")
    practice_subject_quests = fields.Boolean(
        "Subject quests", help="A subject with two or more unlocked decks gets one quest « N sessions of <subject> » "
                               "(any of its decks counts) instead of a quest per deck.")
    practice_unit_access_ids = fields.One2many("homeschool.practice.unit.access", "student_id", string="Units")

    practice_ramp_start = fields.Date(
        "Ramp from", help="With a ramp: the day the learner's bigger day starts growing (week 1).")
    practice_ramp_weeks = fields.Integer(
        "Ramp (weeks)", default=0,
        help="0: the settings apply at once. Else the day's sessions and practice time grow week by week, "
             "linearly, from the defaults in week 1 (3 to 5 sessions, no practice-time quest) to the settings, "
             "reached in the last week. The number of quests does not change: the quests get bigger.")

    @api.constrains("practice_quests_per_day", "practice_sessions_min", "practice_sessions_max", "practice_minutes_goal", "practice_ramp_weeks")
    def _check_practice_day(self):
        for s in self:
            if s.practice_quests_per_day < 1 or s.practice_sessions_min < 1 \
                    or s.practice_sessions_max < s.practice_sessions_min or s.practice_minutes_goal < 0 \
                    or s.practice_ramp_weeks < 0:
                raise ValidationError(self.env._(
                    "Practice settings: at least one quest and one session a day, the maximum of sessions not below "
                    "the minimum, and no negative practice time or ramp."))

    def _practice_volume(self, day=None):
        """The day's effective size: ``{quests, sessions_min, sessions_max, minutes}``.

        ``quests`` is never ramped (a bigger day has bigger quests, not more of them). Without a
        ramp (``practice_ramp_weeks`` = 0 or no start date): the settings. With one: before
        ``practice_ramp_start`` and in week 1 (the start day's week, in the learner's days), the
        defaults; week ``w`` takes ``(w - 1) / (weeks - 1)`` of the gap between the defaults and
        the settings (rounded half up, so never a step backwards); the settings from week
        ``weeks`` on (at once for a one-week ramp). A practice-time goal under
        ``MIN_MINUTES_QUEST`` minutes during the ramp is no quest yet (0)."""
        self.ensure_one()
        me = self.sudo()
        day = day or self._practice_today()
        target = {"quests": me.practice_quests_per_day or DEFAULT_VOLUME["quests"],
                  "sessions_min": max(me.practice_sessions_min or DEFAULT_VOLUME["sessions_min"], 1),
                  "minutes": max(me.practice_minutes_goal, 0)}
        target["sessions_max"] = max(me.practice_sessions_max or DEFAULT_VOLUME["sessions_max"], target["sessions_min"])
        if me.practice_ramp_weeks <= 0 or not me.practice_ramp_start:
            return target
        week = (day - me.practice_ramp_start).days // 7 + 1
        if week < 1:
            share = 0.0
        elif me.practice_ramp_weeks == 1:
            share = 1.0
        else:
            share = min((week - 1) / (me.practice_ramp_weeks - 1), 1.0)
        out = {k: DEFAULT_VOLUME[k] + int((target[k] - DEFAULT_VOLUME[k]) * share + 0.5)
               for k in ("sessions_min", "sessions_max", "minutes")}
        out["quests"] = target["quests"]
        out["sessions_max"] = max(out["sessions_max"], out["sessions_min"])
        if share < 1.0 and out["minutes"] < MIN_MINUTES_QUEST:
            out["minutes"] = 0
        return out

    # ------------------------------------------------------------------
    # the learner's today: every practice date is the learner's, whoever runs the code
    # (the learner through the portal, a parent, a script or a cron with no tz)
    # ------------------------------------------------------------------
    def _practice_tz(self):
        """The learner's time zone: his login's, else his partner's, else the family's (the
        company partner's), else Québec time."""
        self.ensure_one()
        me = self.sudo()
        return me.user_id.tz or me.partner_id.tz or me.company_id.partner_id.tz or DEFAULT_TZ

    def _practice_today(self):
        """Today for the learner (a ``date``)."""
        self.ensure_one()
        return fields.Date.context_today(self.with_context(tz=self._practice_tz()))

    def _practice_local_date(self, moment):
        """The learner's local date of a UTC ``Datetime`` (False when empty)."""
        self.ensure_one()
        if not moment:
            return False
        return fields.Date.context_today(self.with_context(tz=self._practice_tz()), fields.Datetime.to_datetime(moment))

    def _practice_is_practice_day(self, day):
        return str(day.isoweekday()) in (self.sudo().practice_weekdays or "")

    def _practice_needs(self, day):
        """Unlocked units with what they need today, most first: ``[(unit, count, due_seen)]`` —
        ``count`` = new or due items, ``due_seen`` = items already seen and due again (review)."""
        self.ensure_one()
        units = self.env["homeschool.practice.unit.access"].sudo().search(
            [("student_id", "=", self.id), ("state", "=", "unlocked")]).unit_id
        rows = self.env["homeschool.practice.mastery"].sudo().search(
            [("student_id", "=", self.id), ("unit_id", "in", units.ids)])
        out = []
        for unit in units:
            mine = rows.filtered(lambda r: r.unit_id == unit)
            out.append((unit, len(mine.filtered(lambda r: not r.last_seen or r.due_on <= day)),
                        len(mine.filtered(lambda r: r.last_seen and r.due_on <= day))))
        return sorted(out, key=lambda x: (-x[1], x[0].deck_id.sequence, x[0].sequence, x[0].id))

    # ------------------------------------------------------------------
    # practice time (backend; the learner sees the day's minutes on the quest card only)
    # ------------------------------------------------------------------
    def _practice_seconds(self, day):
        """Active practice time on the learner's ``day``, in seconds: over the sessions he
        started that day (any state), each answer counts the gap since the previous answer of
        its session (the first: since the session started), capped at ``GAP_CAP_SECONDS`` so
        an idle screen does not count. Server times (``received_at``), never the device's."""
        self.ensure_one()
        Session = self.env["homeschool.practice.session"].sudo()
        sessions = Session.search([
            ("student_id", "=", self.id),
            ("started_at", ">=", fields.Datetime.to_datetime(day) - timedelta(days=1)),
            ("started_at", "<", fields.Datetime.to_datetime(day) + timedelta(days=2)),
        ]).filtered(lambda s: self._practice_local_date(s.started_at) == day)
        total = 0.0
        for session in sessions:
            prev = session.started_at
            for attempt in session.attempt_ids.sorted(lambda a: (a.received_at, a.id)):
                total += min(max((attempt.received_at - prev).total_seconds(), 0.0), GAP_CAP_SECONDS)
                prev = attempt.received_at
        return int(total)

    def _practice_minutes(self, day):
        """Whole minutes of practice on ``day`` (floor)."""
        return self._practice_seconds(day) // 60
