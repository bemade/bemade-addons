# -*- coding: utf-8 -*-
"""Daily quests: tables until mastered, a rotation of the other decks, surprise lessons; the
learner picks the order; a daily cap."""
import random
from collections import defaultdict
from datetime import date, datetime

from odoo import api, fields, models

QUEST_KINDS = [
    ("deck_session", "Finish sessions in a deck"),
    ("subject_sessions", "Finish sessions in a subject (any of its decks)"),
    ("minutes", "Practice time today (minutes)"),
    ("surprise", "Surprise lessons (a unit the app picks)"),
    ("unit_session", "Finish a session on the unit that needs it most"),
    ("review_session", "Finish a review session"),
    ("no_hint", "Correct answers without a hint"),
    ("perfect", "A session without a miss"),
    ("answers", "Answers given"),
]
# what the day asks for, in sessions (a no-hint quest of one template target ≈ one session);
# the defaults of the learner's practice_sessions_min / practice_sessions_max
DAY_SESSIONS = (3, 5)
MAX_SESSIONS = {"deck_session": 3, "subject_sessions": 4, "surprise": 2, "perfect": 2, "no_hint": 2}
GROWABLE_KINDS = ("deck_session", "subject_sessions", "surprise")  # may ask for more when the day's range needs it
GROW_CEILING = 12  # … up to this many sessions for one quest
DAILY_SHARE = 1 / 3  # a bigger day: the daily decks (tables) get at most about a third of its sessions …
DAILY_CEILING = 5    # … and at most this many
CHALLENGE_KINDS = ("perfect", "no_hint")
SURPRISE_ODDS = 1 / 3      # about one day in three, when a unit is stale
CHALLENGE_ODDS = 1 / 4     # a perfect / no-hint quest takes a rotation slot
STALE_DAYS = 5             # a unit not practised for this many days (or never) is stale
# the practice-time quest comes some days only (owner, 2026-11-24: not every day), more often
# after light days: the learner's mean minutes over his last MINUTES_RECENT_DAYS days with quests
MINUTES_RECENT_DAYS = 3
MINUTES_ODDS = 1 / 3                 # base odds
MINUTES_ODDS_VERY_LIGHT = (0.5, 0.85)  # recent < 50 % of the goal → 0.85
MINUTES_ODDS_LIGHT = (0.75, 0.65)      # recent < 75 % of the goal → 0.65
MINUTES_ODDS_FULL = 0.2              # recent ≥ the goal
MINUTES_MAX_IN_A_ROW = 2             # never 3 days in a row
# « Start » on the practice-time quest (owner, 2026-11-24): a session in a unit picked at random,
# the math facts (daily decks: tables) about a third of the clicks, the other units weighted to
# the longest unseen and the least practised
MINUTES_FACTS_SHARE = 1 / 3
MINUTES_STALE_CAP = 30               # days since last practised count up to this (never practised = this)


class PracticeQuestTemplate(models.Model):
    _name = "homeschool.practice.quest.template"
    _description = "Quest template"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True,
                       help="What the learner reads. May use {unit}, {deck}, {subject}, {target} and {s} (plural mark).")
    sequence = fields.Integer(default=10)
    kind = fields.Selection(QUEST_KINDS, required=True)
    target = fields.Integer(default=1, help="For « no hint » and « answers »: the count for one session's worth.")
    xp = fields.Integer(default=10)
    weight = fields.Integer(default=1, help="Draw frequency in the pool.")
    company_id = fields.Many2one("res.company", help="Empty: available to every family.")
    active = fields.Boolean(default=True)


class PracticeQuest(models.Model):
    _name = "homeschool.practice.quest"
    _description = "Daily quest"
    _inherit = ["homeschool.company.mixin"]
    _order = "day desc, sequence, id"

    student_id = fields.Many2one("homeschool.student", required=True, ondelete="cascade", index=True, check_company=True)
    template_id = fields.Many2one("homeschool.practice.quest.template", required=True, ondelete="restrict")
    kind = fields.Selection(related="template_id.kind", store=True)
    day = fields.Date(required=True, index=True)
    sequence = fields.Integer(default=10)
    deck_id = fields.Many2one("homeschool.practice.deck", ondelete="cascade")
    unit_id = fields.Many2one("homeschool.practice.unit", ondelete="cascade")
    subject_id = fields.Many2one("homeschool.subject", ondelete="cascade", help="Subject quests: any deck of it counts.")
    target = fields.Integer(default=1, help="Sessions, answers, or minutes for the practice-time quest.")
    sessions = fields.Integer(default=1, help="How many sessions of its own the quest asks for: the deck, subject "
                                              "and surprise quests share the learner's day range (a subject quest: "
                                              "beyond its subject's deck quests); a challenge: its own size, done in "
                                              "those sessions; 0 for the practice-time quest.")
    progress = fields.Integer()
    done = fields.Boolean()
    done_at = fields.Datetime()
    label = fields.Char(compute="_compute_label")

    _one_per_template_day = models.Constraint(
        "unique NULLS NOT DISTINCT (student_id, template_id, day, deck_id, unit_id, subject_id)",
        "A quest template is drawn at most once a day per deck, unit and subject.")

    @api.depends("template_id.name", "unit_id.name", "deck_id.name", "subject_id.name", "target")
    @api.depends_context("lang")
    def _compute_label(self):
        french = (self.env.lang or "").startswith("fr")
        for q in self:
            subject = q.subject_id.name or ""
            if french:
                subject = subject.lower()  # « 3 séances de math » : lower case after « de »
            q.label = (q.template_id.name or "").replace("{unit}", q.unit_id.name or "").replace(
                "{deck}", q.deck_id.name or "").replace("{subject}", subject).replace(
                "{target}", str(q.target)).replace("{s}", "s" if q.target > 1 else "")

    # ------------------------------------------------------------------
    # drawing
    # ------------------------------------------------------------------
    @api.model
    def _today(self, student):
        return student._practice_today()

    @api.model
    def _draw(self, student, day=None, rng=None):
        """The day's quests, drawn once (idempotent). None on a rest day or without an unlocked unit.

        The learner's effective volume (``student._practice_volume(day)``: his settings, along
        his ramp) sizes the day: so many quests (never ramped; the practice-time quest is one of
        them), a range of sessions and the practice-time goal. A bigger day makes the quests
        bigger, not more numerous: the deck and subject quests ask for more sessions each (up to
        ``GROW_CEILING``), while the daily decks (tables) keep about a third of a bigger day
        (``DAILY_SHARE``, at most ``DAILY_CEILING``).

        1. every unmastered « daily » deck (times tables) gets a deck session quest;
        2. about one day in three, when a unit is stale, a « surprise lessons » quest — else,
           sometimes, a perfect / no-hint quest — takes a slot;
        3. the other slots rotate among the unlocked decks: least recently quested first
           (ties: most due or new cards), never a deck twice a day; with subject quests on, a
           subject with two or more rotation decks takes one subject quest instead of a quest
           per deck; with too few decks, the remaining slots take a surprise or a challenge;
        4. the targets make the day ask for the learner's range of **distinct** sessions
           (varied; ``_distinct_sessions``): the deck, subject and surprise quests carry the
           drawn total, a perfect / no-hint challenge keeps its own size (1 to 2 sessions'
           worth, done in the day's other sessions), and a subject quest also counts its
           subject's deck quests (tables in math), so its target = its own sessions + theirs;
           the deck and subject quests ask for more each when their usual sizes cannot reach
           the range (with a practice-time quest and a single rotation slot left, only the
           surprise lessons, about one day in three, may take that slot; on a bigger day the
           tables ask for about a third of the sessions);
        5. with a practice-time goal, on some days only (``_minutes_quest_today``), a « practise
           N minutes » quest (no session of its own); the other days, every quest asks for sessions.
        ``rng`` (a ``random.Random``) is injectable; by default it is seeded by learner and day."""
        day = day or self._today(student)
        Quest = self.sudo()
        existing = Quest.search([("student_id", "=", student.id), ("day", "=", day)])
        if existing or not student._practice_is_practice_day(day):
            return existing
        need = student._practice_needs(day)
        if not need:
            return existing
        rng = rng or random.Random("%s-%s" % (student.id, day))
        me = student.sudo()
        volume = student._practice_volume(day)  # the learner's settings, along his ramp
        count = volume["quests"]
        Template = self.env["homeschool.practice.quest.template"].sudo()
        pool = Template.search(["|", ("company_id", "=", False), ("company_id", "=", student.company_id.id)])
        deck_t = pool.filtered(lambda t: t.kind == "deck_session")[:1]
        surprise_t = pool.filtered(lambda t: t.kind == "surprise")[:1]
        subject_t = pool.filtered(lambda t: t.kind == "subject_sessions")[:1] if me.practice_subject_quests else Template
        minutes_t = pool.filtered(lambda t: t.kind == "minutes")[:1] if volume["minutes"] > 0 else Template
        if minutes_t and not self._minutes_quest_today(student, day, volume["minutes"], rng):
            minutes_t = Template
        slots = count - (1 if minutes_t else 0)  # the quests that ask for sessions
        due = defaultdict(int)
        decks = []
        for unit, n, _seen in need:
            due[unit.deck_id] += n
            if unit.deck_id not in decks:
                decks.append(unit.deck_id)
        picks = []  # (template, deck, subject)

        # 1. tables (daily decks) until mastered, those that need it most first
        if deck_t:
            for deck in sorted(decks, key=lambda d: -due[d]):
                if len(picks) < slots and deck.quest_daily and not deck._mastered_by(student):
                    picks.append((deck_t, deck, None))
        mandatory = [d for _t, d, _s in picks]

        # 2. a surprise or a challenge on some days
        stale = student._practice_stale_units(day)
        last_day = Quest.search([("student_id", "=", student.id), ("day", "<", day)], order="day desc", limit=1).day
        yesterday = set(Quest.search([("student_id", "=", student.id), ("day", "=", last_day)]).template_id.ids) \
            if last_day else set()
        challenges = pool.filtered(lambda t: t.kind in CHALLENGE_KINDS)

        def challenge():
            used = {t.id for t, _d, _s in picks}
            rest = challenges.filtered(lambda t: t.id not in used)
            fresh = rest.filtered(lambda t: t.id not in yesterday) or rest
            if not fresh:
                return None
            return rng.choices(list(fresh), weights=[max(t.weight, 1) for t in fresh])[0]

        extra = None
        roll = rng.random()
        if roll < SURPRISE_ODDS:
            extra = surprise_t if stale else None
        elif roll < SURPRISE_ODDS + CHALLENGE_ODDS:
            extra = challenge()
        if minutes_t and slots - len(mandatory) < 2:
            # the practice-time quest took a slot: the one rotation slot left stays a deck / subject
            # quest, or becomes the surprise lessons (about one day in three); never a challenge
            extra = extra if extra == surprise_t else None

        # 3. the rotation: least recently quested first, ties to the most due
        last = {}
        if deck_t:
            for q in Quest.search([("student_id", "=", student.id), ("day", "<", day), ("deck_id", "!=", False),
                                   ("kind", "=", "deck_session")], order="day asc"):
                last[q.deck_id.id] = q.day
        rotation_decks = [d for d in decks if d not in mandatory]
        by_subject = defaultdict(int)
        if subject_t:
            for d in rotation_decks:
                if d.subject_id:
                    by_subject[d.subject_id] += 1
            for q in Quest.search([("student_id", "=", student.id), ("day", "<", day), ("subject_id", "!=", False),
                                   ("kind", "=", "subject_sessions")], order="day asc"):
                for d in rotation_decks:
                    if d.subject_id == q.subject_id:
                        last[d.id] = max(last.get(d.id, date.min), q.day)
        rotation = sorted(rotation_decks, key=lambda d: (last.get(d.id, date.min), -due[d], d.sequence, d.id))
        if deck_t:
            subjects = set()
            for deck in rotation:
                if len(picks) >= slots - (1 if extra else 0):
                    break
                if by_subject.get(deck.subject_id, 0) >= 2:
                    if deck.subject_id not in subjects:
                        subjects.add(deck.subject_id)
                        picks.append((subject_t, None, deck.subject_id))
                    continue
                picks.append((deck_t, deck, None))
        if extra and len(picks) < slots:
            picks.append((extra, None, None))
        # too few decks: fill with a surprise (when a unit is stale), then challenges
        if len(picks) < slots and surprise_t and stale and surprise_t not in [t for t, _d, _s in picks]:
            picks.append((surprise_t, None, None))
        while len(picks) < slots:
            t = challenge()
            if not t:
                break
            picks.append((t, None, None))

        # 4. targets: the day asks for the learner's range of distinct sessions (varied). The
        # challenges are done in the other quests' sessions: they carry none of the total (unless
        # the day has nothing else).
        lo_day, hi_day = volume["sessions_min"], volume["sessions_max"]
        carry = [i for i, (t, _d, _s) in enumerate(picks) if t.kind not in CHALLENGE_KINDS] or list(range(len(picks)))
        caps = {i: MAX_SESSIONS.get(picks[i][0].kind, 1) for i in carry}
        daily = [i for i in carry if picks[i][0].kind == "deck_session" and picks[i][1] in mandatory]
        growable = [i for i in carry if picks[i][0].kind in GROWABLE_KINDS]

        def daily_limit(total):
            """A day bigger than the defaults: the daily decks get about a third of it, at most
            DAILY_CEILING each (the defaults keep their sizes)."""
            if total <= DAY_SESSIONS[1]:
                return None
            return max(1, min(DAILY_CEILING, int(total * DAILY_SHARE + 0.5)))

        def grow(target):
            limit = daily_limit(target)
            if limit is not None:
                for i in daily:
                    caps[i] = min(caps[i], limit) if caps[i] > limit else caps[i]
            ceiling = {i: (limit if i in daily and limit is not None else GROW_CEILING) for i in growable}
            while sum(caps.values()) < target and any(caps[i] < ceiling[i] for i in growable):
                for i in growable:
                    if sum(caps.values()) < target and caps[i] < ceiling[i]:
                        caps[i] += 1

        grow(hi_day)
        sessions = [1] * len(picks)
        if carry:
            lo, hi = max(lo_day, len(carry)), max(min(hi_day, sum(caps.values())), len(carry))
            total = rng.choice(range(min(lo, hi), hi + 1))
            grow(total)  # the tables' third of the day actually drawn; the others take the rest
            for _i in range(total - len(carry)):
                room = [i for i in carry if sessions[i] < caps[i]]
                if not room:
                    break
                sessions[rng.choice(room)] += 1
            day_total = sum(sessions[i] for i in carry)
            for i in range(len(picks)):
                if i not in caps:  # a challenge: its own size, never more than the day
                    sessions[i] = rng.randint(1, max(1, min(MAX_SESSIONS.get(picks[i][0].kind, 1), day_total)))
        # a subject quest also counts its subject's deck quests (tables in math): it asks for
        # its own sessions beyond theirs
        overlap = defaultdict(int)
        for (t, deck, _s), n in zip(picks, sessions):
            if t.kind == "deck_session" and deck.subject_id:
                overlap[deck.subject_id] += n
        start_deck = need[0][0].deck_id
        vals = []
        for (t, deck, subject), n in zip(picks, sessions):
            if t.kind in ("no_hint", "answers"):
                target = n * max(t.target, 1)
            elif t.kind == "subject_sessions":
                target = n + overlap[subject]
            else:
                target = n
            if not deck and t.kind in CHALLENGE_KINDS:
                deck = start_deck  # where « Start » opens a session
            vals.append(dict(student_id=student.id, template_id=t.id, day=day, sequence=len(vals), sessions=n,
                             target=target, deck_id=deck.id if deck else False,
                             subject_id=subject.id if subject else False))

        # 5. the practice-time quest: no session of its own; progress = today's minutes so far
        if minutes_t:
            goal = volume["minutes"]
            done_min = min(student._practice_minutes(day), goal)
            vals.append(dict(student_id=student.id, template_id=minutes_t.id, day=day, sequence=len(vals), sessions=0,
                             target=goal, progress=done_min, done=done_min >= goal,
                             done_at=fields.Datetime.now() if done_min >= goal else False, deck_id=start_deck.id))
        return Quest.create(vals)

    @api.model
    def _minutes_quest_today(self, student, day, goal, rng):
        """Whether the day carries the practice-time quest (a goal of ``goal`` minutes): about
        one day in three (``MINUTES_ODDS``), more often after light days, less after full ones:
        recent = the learner's mean practice minutes over his last ``MINUTES_RECENT_DAYS`` days
        with quests (a day without practice counts 0); never more than
        ``MINUTES_MAX_IN_A_ROW`` days in a row. ``rng`` is the draw's (seeded by learner and day)."""
        Quest = self.sudo()
        past = Quest.search([("student_id", "=", student.id), ("day", "<", day)], order="day desc")
        days = []
        for q in past:
            if q.day not in days:
                days.append(q.day)
        streak = days[:MINUTES_MAX_IN_A_ROW]
        if len(streak) == MINUTES_MAX_IN_A_ROW and all(
                past.filtered(lambda q, d=d: q.day == d and q.kind == "minutes") for d in streak):
            return False
        odds = MINUTES_ODDS
        recent_days = days[:MINUTES_RECENT_DAYS]
        if recent_days and goal > 0:
            recent = sum(student._practice_minutes(d) for d in recent_days) / len(recent_days)
            if recent < goal * MINUTES_ODDS_VERY_LIGHT[0]:
                odds = MINUTES_ODDS_VERY_LIGHT[1]
            elif recent < goal * MINUTES_ODDS_LIGHT[0]:
                odds = MINUTES_ODDS_LIGHT[1]
            elif recent >= goal:
                odds = MINUTES_ODDS_FULL
        return rng.random() < odds

    @api.model
    def _distinct_sessions(self, vals=None):
        """The fewest finished sessions that complete every session quest of a day, overlaps
        included (the day's quests as records, or ``vals``: dicts with ``template_id``,
        ``target`` and ``deck_id`` / ``subject_id``). A session of a deck counts for its deck
        quest and for its subject's quest: per subject quest, the bigger of its target and its
        subject's deck quests' targets; the other deck quests, the surprise lessons (their rare
        overlap with a deck quest is not counted) and the unit / review quests on their own. A
        perfect / no-hint / answers quest is done in those sessions, unless it asks for more
        sessions than they make. The practice-time quest asks for none."""
        if vals is None:
            vals = [dict(template_id=q.template_id.id, target=q.target, deck_id=q.deck_id.id,
                         subject_id=q.subject_id.id) for q in self]
        Template = self.env["homeschool.practice.quest.template"].sudo()
        Deck = self.env["homeschool.practice.deck"].sudo()
        by_subject, by_deck = defaultdict(int), defaultdict(int)
        alone = challenge = 0
        for v in vals:
            t = Template.browse(v["template_id"])
            target = v.get("target") or 0
            if t.kind == "subject_sessions":
                by_subject[v.get("subject_id")] = max(by_subject[v.get("subject_id")], target)
            elif t.kind == "deck_session":
                by_deck[v.get("deck_id")] = max(by_deck[v.get("deck_id")], target)
            elif t.kind in ("no_hint", "answers"):
                challenge = max(challenge, -(-target // max(t.target, 1)))
            elif t.kind == "perfect":
                challenge = max(challenge, target)
            elif t.kind != "minutes":
                alone += target
        tables = defaultdict(int)  # the deck quests inside a subject quest's subject
        for deck_id, n in by_deck.items():
            subject = Deck.browse(deck_id).subject_id.id
            if subject and subject in by_subject:
                tables[subject] += n
            else:
                alone += n
        base = alone + sum(max(n, tables[s]) for s, n in by_subject.items())
        return max(base, challenge)

    def _subject_deck(self):
        """The deck a subject quest's « Start » opens: an unlocked deck of the subject, one
        without a deck quest of its own today when possible, the one practised least today
        (then the one practised longest ago; then the deck order)."""
        self.ensure_one()
        student = self.student_id
        decks = self.env["homeschool.practice.unit.access"].sudo().search(
            [("student_id", "=", student.id), ("state", "=", "unlocked")]).deck_id.filtered(
            lambda d: d.subject_id == self.subject_id)
        own = self.search([("student_id", "=", student.id), ("day", "=", self.day),
                           ("kind", "=", "deck_session")]).deck_id
        candidates = (decks - own) or decks
        Session = self.env["homeschool.practice.session"].sudo()
        done = Session.search([("student_id", "=", student.id), ("state", "=", "done"), ("item_count", ">", 0),
                               ("deck_id", "in", candidates.ids)])
        today = defaultdict(int)
        last = {}
        for s in done:
            if student._practice_local_date(s.started_at) == self.day:
                today[s.deck_id.id] += 1
            last[s.deck_id.id] = max(last.get(s.deck_id.id, s.started_at), s.started_at)
        return min(candidates, key=lambda d: (today[d.id], last.get(d.id, datetime.min), d.sequence, d.id)) \
            if candidates else candidates

    def _surprise_unit(self):
        """The unit a surprise session opens: the stale unlocked unit practised longest ago
        (never first; tie: most due cards), outside the day's other quest decks when possible;
        with no stale unit, the unit practised longest ago."""
        self.ensure_one()
        student = self.student_id
        others = self.search([("student_id", "=", student.id), ("day", "=", self.day), ("id", "!=", self.id)]).deck_id
        ranked = student._practice_units_by_staleness(self.day)
        stale = [r for r in ranked if r[1]]
        for pool in ([r for r in stale if r[0].deck_id not in others], stale, ranked):
            if pool:
                return pool[0][0]
        return self.env["homeschool.practice.unit"]

    def _minutes_unit(self, rng=None):
        """Where the practice-time quest's « Start » opens a session: ``(deck, unit, kind)``,
        a new random pick at every click (the learner does not choose; the quest's own
        ``deck_id`` is not used). With probability ``MINUTES_FACTS_SHARE`` the math facts:
        a daily deck (``quest_daily``: tables; the one with most due or new cards), its unit
        that needs it most (``kind`` « unit »), else a review of the deck when nothing is new
        or due (tables mastered). Otherwise a weighted pick among the learner's other unlocked
        units (``kind`` « unit »), weight = ``(1 + d) × (1 + 1 / (1 + n))``: ``d`` = days since
        the unit's last session of its own (``_practice_last_practised``), at most
        ``MINUTES_STALE_CAP`` (never practised = the cap), ``n`` = its finished sessions of its
        own; the unit of the learner's last session today is left out when another exists.
        With no daily deck the share is 0; with no other unit, always the facts. Empty records
        and ``None`` kind when the learner has no unlocked unit. ``rng``: the system's by default
        (each click differs), injectable for tests."""
        self.ensure_one()
        rng = rng or random.SystemRandom()
        student = self.student_id
        Unit = self.env["homeschool.practice.unit"]
        day = student._practice_today()
        needs = student._practice_needs(day)
        if not needs:
            return self.env["homeschool.practice.deck"], Unit, None
        daily = [n for n in needs if n[0].deck_id.quest_daily]
        others = [n for n in needs if not n[0].deck_id.quest_daily]
        if daily and (not others or rng.random() < MINUTES_FACTS_SHARE):
            due = defaultdict(int)
            for unit, count, _seen in daily:
                due[unit.deck_id] += count
            deck = min(due, key=lambda d: (-due[d], d.sequence, d.id))
            mine = [n for n in daily if n[0].deck_id == deck]  # most needed first (``_practice_needs``)
            if mine[0][1]:
                return deck, mine[0][0], "unit"
            seen = self.env["homeschool.practice.mastery"].sudo().search_count(
                [("student_id", "=", student.id), ("deck_id", "=", deck.id), ("last_seen", "!=", False)])
            return (deck, Unit, "review") if seen else (deck, mine[0][0], "unit")
        history = student._practice_unit_history()
        Session = self.env["homeschool.practice.session"].sudo()
        last_today = Session.search([("student_id", "=", student.id), ("kind", "=", "unit")],
                                    order="started_at desc, id desc", limit=1)
        if last_today and student._practice_local_date(last_today.started_at) != day:
            last_today = Session
        units = [n[0] for n in others]
        if len(units) > 1 and last_today.unit_id in units:
            units.remove(last_today.unit_id)
        weights = []
        for unit in units:
            count, when = history.get(unit.id, (0, None))
            days = MINUTES_STALE_CAP if when is None else min(
                max((day - student._practice_local_date(when)).days, 0), MINUTES_STALE_CAP)
            weights.append((1 + days) * (1 + 1 / (1 + count)))
        unit = rng.choices(units, weights=weights)[0]
        return unit.deck_id, unit, "unit"

    # ------------------------------------------------------------------
    # progress (only today's events count; capped once the day's quests are done)
    # ------------------------------------------------------------------
    def _bump(self, amount=1):
        done = self.browse()
        for q in self.filtered(lambda q: not q.done):
            q.progress = min(q.progress + amount, q.target)
            if q.progress >= q.target:
                q.write({"done": True, "done_at": fields.Datetime.now()})
                done |= q
        return done

    def _refresh_minutes(self):
        """Practice-time quests: progress = the learner's whole minutes of practice that day."""
        done = self.browse()
        for q in self.filtered(lambda q: q.kind == "minutes" and not q.done):
            q.progress = min(q.student_id._practice_minutes(q.day), q.target)
            if q.progress >= q.target:
                q.write({"done": True, "done_at": fields.Datetime.now()})
                done |= q
        return done


class PracticeSession(models.Model):
    _inherit = "homeschool.practice.session"

    def _todays_quests(self):
        Quest = self.env["homeschool.practice.quest"].sudo()
        return Quest.search([("student_id", "=", self.student_id.id), ("day", "=", Quest._today(self.student_id))])

    def _quests_done(self, events, quests):
        if not quests:
            return
        events.setdefault("quests_done", []).extend(quests.ids)
        for q in quests:
            self._xp_award(events, q.template_id.xp, "quest", q)
        self._on_quests_done(events, quests)

    def _on_quests_done(self, events, quests):
        """Hook for goals (day / week / month)."""
        return events

    def _after_answer(self, attempt, events):
        res = super()._after_answer(attempt, events)
        quests = self._todays_quests().filtered(lambda q: not q.done)
        done = quests.filtered(lambda q: q.kind == "answers")._bump()
        if attempt.correct and not attempt.hint_used:
            done |= quests.filtered(lambda q: q.kind == "no_hint")._bump()
        done |= quests.filtered(lambda q: q.kind == "minutes")._refresh_minutes()
        self._quests_done(events, done)
        return res

    def _after_finish(self, events):
        res = super()._after_finish(events)
        if not self.item_count:
            return res
        quests = self._todays_quests().filtered(lambda q: not q.done)
        done = quests.filtered(lambda q: q.kind == "deck_session" and q.deck_id == self.deck_id)._bump()
        if self.deck_id.subject_id:
            done |= quests.filtered(
                lambda q: q.kind == "subject_sessions" and q.subject_id == self.deck_id.subject_id)._bump()
        if self.quest_id.kind == "surprise":
            done |= (quests & self.quest_id.sudo())._bump()
        if self.kind == "unit":
            done |= quests.filtered(lambda q: q.kind == "unit_session" and q.unit_id == self.unit_id)._bump()
        if self.kind == "review":
            done |= quests.filtered(lambda q: q.kind == "review_session")._bump()
        if self.kind == "free" and len(self.unit_ids) == 1:
            done |= quests.filtered(lambda q: q.kind == "unit_session" and q.unit_id == self.unit_ids)._bump()
        if self.perfect:
            done |= quests.filtered(lambda q: q.kind == "perfect")._bump()
        self._quests_done(events, done)
        return res


class Student(models.Model):
    _inherit = "homeschool.student"

    def _practice_last_practised(self):
        """``{unit id: datetime}``: when each unit last had a finished session of its own (a unit
        session, or free practice on it). Review sessions do not count."""
        return {unit_id: when for unit_id, (_count, when) in self._practice_unit_history().items()}

    def _practice_unit_history(self):
        """``{unit id: (sessions, last datetime)}``: each unit's finished sessions of its own (a
        unit session, or free practice on it) and when the last one started. Review sessions do
        not count."""
        self.ensure_one()
        Session = self.env["homeschool.practice.session"].sudo()
        base = [("student_id", "=", self.id), ("state", "=", "done"), ("item_count", ">", 0)]
        out = {unit.id: (count, when) for unit, count, when in Session._read_group(
            base + [("kind", "=", "unit"), ("unit_id", "!=", False)], ["unit_id"], ["__count", "started_at:max"])}
        for s in Session.search(base + [("kind", "=", "free")]):
            for unit in s.unit_ids:
                count, when = out.get(unit.id, (0, s.started_at))
                out[unit.id] = (count + 1, max(when, s.started_at))
        return out

    def _practice_units_by_staleness(self, day):
        """The unlocked units, practised longest ago first (never practised first; tie: most due
        or new cards): ``[(unit, stale)]``, stale = not practised for ``STALE_DAYS`` days or never."""
        self.ensure_one()
        last = self._practice_last_practised()
        rows = []
        for unit, count, _seen in self._practice_needs(day):
            when = last.get(unit.id)
            stale = when is None or (day - self._practice_local_date(when)).days >= STALE_DAYS
            rows.append(((when or datetime.min, -count, unit.deck_id.sequence, unit.sequence, unit.id), unit, stale))
        rows.sort(key=lambda r: r[0])
        return [(unit, stale) for _key, unit, stale in rows]

    def _practice_stale_units(self, day):
        return self.env["homeschool.practice.unit"].browse(
            [unit.id for unit, stale in self._practice_units_by_staleness(day) if stale])
