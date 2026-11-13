# -*- coding: utf-8 -*-
"""The practice API every front end uses (the portal lesson screen now, games later).

Only the learner himself (``student.user_id``) may call it. Every payload is built by hand
from an allowlist: no latency, threshold, timer, time limit or mastery verdict ever leaves
the server (UC-11 §5)."""
from werkzeug.exceptions import Forbidden, NotFound

from odoo import fields, http
from odoo.exceptions import UserError
from odoo.http import request

API = "/my/homeschool/practice/api"
FORBIDDEN_KEYS = {"first_touch_ms", "submit_ms", "latency", "threshold", "timer", "time_limit", "state", "box",
                  "due_on", "became_automatic", "outlier"}


def learner_labels(env):
    _ = env._
    return {
        "title": _("Practice"), "level": _("Level"), "xp": _("XP"), "quests": _("Today's quests"),
        "rest_day": _("Rest day! No quests today. You can still practice for fun."),
        "goals": _("Goals"), "day": _("Today"), "week": _("This week"), "month": _("This month"),
        "bank": _("In the bank"), "badges": _("Badges"), "start": _("Start"), "done": _("Done!"),
        "free": _("Free practice"), "check": _("Check"), "erase": _("Erase"), "hint": _("A hint"),
        "continue": _("Continue"), "great": _("Great!"), "almost": _("Almost!"), "answer_is": _("The answer is"),
        "session_done": _("Session finished!"), "answers": _("answers"), "correct": _("correct"),
        "quest_done": _("Quest complete!"), "goal_day": _("Daily goal reached!"),
        "goal_week": _("Weekly goal reached!"), "goal_month": _("Monthly goal reached!"),
        "level_up": _("New level!"), "new_badge": _("New badge!"), "unit_unlocked": _("New unit!"), "reward": _("Reward"),
        "home": _("Back"), "offline": _("Connection lost: your answer is saved, retrying…"),
        "nothing": _("Nothing to practice here yet."), "new_unit": _("Something new!"), "got_it": _("Got it!"),
        "well_done": _("Well done for practicing!"), "pick": _("Choose what to practice"), "all": _("All"),
    }


class PracticeApi(http.Controller):

    def _student(self):
        uid = request.env.uid
        student = request.env["homeschool.student"].sudo().search([("user_id", "=", uid)], limit=1)
        if not student or request.env.user._is_internal():
            raise Forbidden()
        return student

    def _today(self, student):
        return request.env["homeschool.practice.quest"].sudo()._today(student)

    # ------------------------------------------------------------------
    # serializers (allowlists)
    # ------------------------------------------------------------------
    def _item_payload(self, session):
        item = session._current_item()
        if not item:
            return None
        access = request.env["homeschool.practice.unit.access"].sudo().search(
            [("student_id", "=", session.student_id.id), ("unit_id", "=", item.unit_id.id)], limit=1)
        first_time = bool(access) and not access.first_served
        if first_time:
            access.first_served = True
        return {
            "item_id": item.id, "prompt": item.prompt, "answer_mode": item.answer_mode,
            "choices": item.choice_ids.sorted(lambda c: (c.sequence, c.id)).mapped("label") if item.answer_mode == "choices" else [],
            "hint": item.hint or "", "unit": item.unit_id.name,
            "intro": (item.unit_id.intro or "") if first_time else "", "first_time": first_time,
            "index": session.position + 1, "total": len(session._queue()),
        }

    def _quest_payload(self, q):
        return {"id": q.id, "label": q.label, "kind": q.kind, "progress": q.progress, "target": q.target,
                "done": q.done, "unit": q.unit_id.name or ""}

    def _events_payload(self, events, student):
        Quest = request.env["homeschool.practice.quest"].sudo()
        Badge = request.env["homeschool.practice.badge"].sudo()
        out = {"xp": events.get("xp", 0)}
        if events.get("level_up"):
            out["level_up"] = {"from": events["level_up"]["from"], "to": events["level_up"]["to"]}
        out["quests_done"] = [q.label for q in Quest.browse(events.get("quests_done", []))]
        out["goals_reached"] = list(events.get("goals_reached", []))
        out["badges"] = [{"name": b.template_id.name, "icon": b.template_id.icon,
                          "unit": b.unit_id.name or ""} for b in Badge.browse(events.get("badges", []))]
        out["rewards"] = [dict(r) for r in events.get("rewards", [])]
        out["units_unlocked"] = request.env["homeschool.practice.unit"].sudo().browse(
            events.get("units_unlocked", [])).mapped("name")
        return out

    # ------------------------------------------------------------------
    # routes
    # ------------------------------------------------------------------
    @http.route(API + "/home", type="jsonrpc", auth="user")
    def home(self):
        student = self._student()
        today = self._today(student)
        quests = request.env["homeschool.practice.quest"].sudo()._draw(student, today)
        xp = student.practice_xp
        level = student.practice_level
        badges = request.env["homeschool.practice.badge"].sudo().search([("student_id", "=", student.id)])
        payload = {
            "labels": learner_labels(request.env),
            "name": student.name.split(" ")[0] if student.name else "",
            "handedness": student.practice_handedness,
            "rest_day": not student._practice_is_practice_day(today),
            "level": level, "xp": xp,
            "xp_level_start": student._practice_level_req(level),
            "xp_next_level": student._practice_level_req(level + 1),
            "quests": [self._quest_payload(q) for q in quests],
            "goals": student._practice_goal_progress(today),
            "balances": student._practice_balances(),
            "badges": [{"name": b.template_id.name, "icon": b.template_id.icon, "unit": b.unit_id.name or "",
                        "new": not b.seen} for b in badges[:12]],
            "badge_count": len(badges),
            "decks": [{"id": d.id, "name": d.name, "units": [{"id": u.id, "name": u.name} for u in self._units(student, d)]}
                      for d in self._decks(student)],
        }
        badges.filtered(lambda b: not b.seen).write({"seen": True})
        return payload

    def _decks(self, student):
        return request.env["homeschool.practice.unit.access"].sudo().search(
            [("student_id", "=", student.id), ("state", "=", "unlocked")]).deck_id.sorted(lambda d: (d.sequence, d.id))

    def _units(self, student, deck):
        return deck.unit_ids._unlocked_for(student).sorted(lambda u: (u.sequence, u.id))

    @http.route(API + "/session/start", type="jsonrpc", auth="user")
    def session_start(self, quest_id=None, deck_id=None, unit_ids=None, device=None, input_type="touch",
                      frontend="portal_lesson"):
        student = self._student()
        Session = request.env["homeschool.practice.session"].sudo()
        quest = request.env["homeschool.practice.quest"].sudo().browse(int(quest_id)) if quest_id else None
        if quest and (not quest.exists() or quest.student_id != student):
            raise NotFound()
        decks = self._decks(student)
        deck = quest.deck_id if quest else request.env["homeschool.practice.deck"].sudo().browse(int(deck_id or 0))
        if deck not in decks:
            raise NotFound()
        units = None
        needs = [n for n in student._practice_needs(self._today(student)) if n[0].deck_id == deck]
        if not quest and unit_ids:
            units = request.env["homeschool.practice.unit"].sudo().browse([int(u) for u in unit_ids]).exists()
            if len(units) != len(set(unit_ids)) or units - self._units(student, deck):
                raise NotFound()
            kind, unit = "free", None
        elif quest and quest.kind == "review_session":
            kind, unit = "review", None
        elif quest:
            kind, unit = "unit", quest.unit_id or (needs[0][0] if needs else None)
        else:
            seen = request.env["homeschool.practice.mastery"].sudo().search_count(
                [("student_id", "=", student.id), ("deck_id", "=", deck.id), ("last_seen", "!=", False)])
            kind, unit = ("unit", needs[0][0]) if needs and needs[0][1] else ("review", None)
            if kind == "review" and not seen and needs:
                kind, unit = "unit", needs[0][0]
        if kind == "unit" and not unit:
            kind = "review"
        if input_type not in ("touch", "mouse", "keyboard"):
            input_type = "touch"
        session = Session._start(student, deck, kind=kind, unit=unit, units=units, quest=quest, device=(device or "")[:120],
                                 input_type=input_type, frontend=(frontend or "portal_lesson")[:60])
        return {"session_id": session.id, "item": self._item_payload(session)}

    def _session(self, student, session_id):
        session = request.env["homeschool.practice.session"].sudo().browse(int(session_id or 0))
        if not session.exists() or session.student_id != student:
            raise NotFound()
        return session

    @http.route(API + "/session/answer", type="jsonrpc", auth="user")
    def session_answer(self, session_id, item_id, given, hint_used=False, first_touch_ms=0, submit_ms=0,
                       client_ts=None, client_uuid=None):
        student = self._student()
        session = self._session(student, session_id)
        item = request.env["homeschool.practice.item"].sudo().browse(int(item_id))
        ts = None
        if client_ts:
            try:
                ts = fields.Datetime.to_datetime(str(client_ts).replace("T", " ").replace("Z", "")[:19])
            except ValueError:
                ts = None
        try:
            attempt, events = session._answer(item, str(given or "")[:64], hint_used=bool(hint_used),
                                              first_touch_ms=first_touch_ms, submit_ms=submit_ms,
                                              client_ts=ts, client_uuid=(client_uuid or None) and str(client_uuid)[:64])
        except UserError:
            return {"error": "stale", "item": self._item_payload(session), "done": session.state != "open"}
        out = {"correct": attempt.correct}
        if not attempt.correct:
            out.update(expected=item.answer, hint=item.hint or "")
        out.update(self._events_payload(events, student))
        nxt = self._item_payload(session)
        if nxt:
            out["next"] = nxt
        else:
            fin = session._finish()
            out["done"] = True
            out["summary"] = self._summary(session, fin, student)
        return out

    def _summary(self, session, events, student):
        out = {"answers": session.item_count, "correct": session.correct_count}
        ev = self._events_payload(events, student)
        ev["xp_session"] = sum(request.env["homeschool.practice.xp"].sudo().search([
            ("student_id", "=", student.id),
            "|", ("source", "=", "homeschool.practice.session,%s" % session.id),
            ("source", "in", ["homeschool.practice.attempt,%s" % a for a in session.attempt_ids.ids])]).mapped("amount"))
        out.update(ev)
        return out

    @http.route(API + "/session/finish", type="jsonrpc", auth="user")
    def session_finish(self, session_id):
        student = self._student()
        session = self._session(student, session_id)
        events = session._finish()
        return {"summary": self._summary(session, events, student)}
