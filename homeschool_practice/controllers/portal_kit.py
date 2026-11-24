# -*- coding: utf-8 -*-
# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Practice in the homeschool portal app: « Today »'s quests widget and the
tutor's progress page (``models/portal_kit.py``).

What a learner may see never includes the mastery state, a box, a threshold
or a timing (UC-11 §5): the quests widget carries the quest's label, its
progress and whether it is done, nothing else. The progress page (proficiency
per unit) is for the adults who follow the learner (``tutor``): the learner's
own login gets a 403 there, even on a student he also follows."""
from werkzeug.exceptions import Forbidden

from odoo import http
from odoo.http import request
from odoo.tools import format_date

from odoo.addons.homeschool_portal.controllers.portal import HomeschoolPortal

from ..models.portal_kit import PRACTICE_URL


class HomeschoolPracticeShell(HomeschoolPortal):

    # ------------------------------------------------------------------
    # « Today »: the day's quests
    # ------------------------------------------------------------------
    def _hs_dash_quests(self, instance, scope, ctx):
        """The learner's quests of the day (drawn once a day, as the game does). The
        learner gets « Start » on each open quest; a tutor reads them."""
        student = ctx.get("hs_student")
        values = {"hs_quests": [], "hs_rest_day": False, "list_url": False}
        if not student:
            return values
        student = student.sudo()
        Quest = request.env["homeschool.practice.quest"].sudo()
        today = Quest._today(student)
        learner = ctx.get("hs_role") == "student"
        quests = Quest._draw(student, today)
        values.update({
            "hs_rest_day": not student._practice_is_practice_day(today),
            "hs_quests": [{
                "id": q.id, "label": q.label, "progress": min(q.progress, q.target), "target": q.target,
                "done": q.done, "minutes": q.kind == "minutes",
                "start_url": "%s?quest=%d" % (PRACTICE_URL, q.id) if learner and not q.done else False,
            } for q in quests],
            "hs_practice_url": PRACTICE_URL if learner else False,
            "list_url": PRACTICE_URL if learner else "/my/homeschool/%d/practice/progress" % student.id,
        })
        return values

    # ------------------------------------------------------------------
    # the tutor's progress page
    # ------------------------------------------------------------------
    @http.route(["/my/homeschool/practice/progress"], type="http", auth="user", website=True)
    def portal_practice_progress_current(self, **kw):
        """The nav entry: the progress of the learner the tutor is looking at."""
        students = self._portal_students().filtered(lambda s: self._portal_role(s) == "resource")
        if not students:
            raise Forbidden()
        student = self._hs_current_student(students)
        return request.redirect("/my/homeschool/%d/practice/progress" % student.id)

    @http.route(["/my/homeschool/<int:student_id>/practice/progress"], type="http", auth="user", website=True)
    def portal_practice_progress(self, student_id, **kw):
        """Read-only, per learner: the units unlocked by deck, the proficiency of each
        (share of its items that are secure), how often it was practised (sessions that
        asked it, answers given) and when it was last practised. For a
        resource user of the student only (never the learner himself)."""
        student = self._portal_student(student_id)
        if self._portal_role(student) != "resource":
            raise Forbidden()
        env = request.env
        Access = env["homeschool.practice.unit.access"].sudo()
        Mastery = env["homeschool.practice.mastery"].sudo()
        Attempt = env["homeschool.practice.attempt"].sudo()
        rows = Access.search([("student_id", "=", student.id), ("state", "=", "unlocked")])
        decks = []
        for deck in rows.deck_id.sorted(lambda d: (d.sequence, d.id)):
            units = []
            deck_rows = rows.filtered(lambda r, d=deck: r.deck_id == d)
            for row in deck_rows.sorted(lambda r: (r.unit_id.sequence, r.unit_id.id)):
                unit = row.unit_id
                last = Mastery.search([("student_id", "=", student.id), ("unit_id", "=", unit.id),
                                       ("last_seen", "!=", False)], order="last_seen desc", limit=1).last_seen
                attempts = Attempt.search([("session_id.student_id", "=", student.id), ("item_id.unit_id", "=", unit.id)])
                units.append({
                    "unit": unit,
                    "sessions": len(attempts.session_id),
                    "answers": len(attempts),
                    "proficiency": unit._proficiency(student),
                    "unlocked_on": format_date(env, row.unlocked_on) if row.unlocked_on else "",
                    "last_practised": format_date(env, student._practice_local_date(last)) if last else "",
                })
            decks.append({"deck": deck, "units": units})
        values = self._homeschool_values(student, "homeschool_practice_progress")
        values.update({"decks": decks})
        return self._hs_render("homeschool_practice.portal_practice_progress", values, "hs_practice_progress",
                               title=env._("Practice"), active_nav="hs_practice_progress")
