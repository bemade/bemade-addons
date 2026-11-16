# -*- coding: utf-8 -*-
"""Portal pages of ``homeschool``.

Every page starts by resolving the student from the URL against the user's relation to
him (his own student, or a student he is attached to as a resource user); an unrelated
or unknown student is a 404. Records are then searched **as the portal user**, so the
record rules of ``homeschool`` decide what is listed; writes (tick, reading entry,
submitted trace and its files) run as the user too, so the core access lines, rules and
model guards apply. Nothing here runs as superuser: the student record, the subjects,
the files of a trace or a material all come back through the core's own portal access
(``homeschool`` 19.0.5.0.0 and later — a file follows the record it is linked to).

The app (19.0.3.0.0): while the Bemade portal kit's switch is on (Settings › Portal App)
and the user is in the kit app ``homeschool`` (a ``learner`` / ``tutor`` role,
``models/portal_kit.py``), every page is drawn in the kit's shell
(``homeschool_portal.hs_app_layout``) and ``/my/home`` is « Today », the kit's dashboard
of the learner's day (the app's ``home_render``, ``_hs_dash_render``). The kit hooks here
answer for the homeschool app only (``super()`` for any other app of the database).
Otherwise the same
templates are drawn on the stock portal layout: the routes, the URLs, the data and the
permissions are the same either way (``_hs_render``).

A tutor may follow several learners: the URLs carry the student, the app bar has a
learner switcher, and the last learner looked at is remembered in the session for the
pages whose URL carries none (« Today », the nav entries).
"""
from datetime import date, timedelta

from werkzeug.exceptions import Forbidden, NotFound
from werkzeug.utils import secure_filename

from odoo import fields, http
from odoo.exceptions import AccessError
from odoo.fields import Command
from odoo.http import request
from odoo.tools import format_date

from odoo.addons.bemade_portal_kit.tools import pk_safe_return_url
from odoo.addons.bemade_portal_kit_dashboard.controllers.pk_dashboard import PortalKitDashboard
from odoo.addons.homeschool.models.day import iso_week_label
from odoo.addons.portal.controllers.portal import pager as portal_pager

from ..models.portal_kit import HS_APP, HS_HOME_URL, HS_LAYOUT, HS_LEARNER, HS_TUTOR, hs_user_roles

MAX_FILES = 10
MAX_TOTAL_MB = 25
WEEK_DAYS = 5
STOCK_LAYOUT = "portal.portal_layout"
# The session key of the learner a tutor is looking at.
SESSION_STUDENT = "hs_student_id"
# The sections a nav entry opens for the current learner (/my/homeschool/<section>).
SECTIONS = ("day", "week", "traces", "reading")


def _fmt_hour(value):
    """9.25 -> '09:15'."""
    hours = int(value or 0)
    minutes = int(round(((value or 0) - hours) * 60))
    if minutes == 60:
        hours, minutes = hours + 1, 0
    return "%02d:%02d" % (hours, minutes)


def _parse_date(text):
    try:
        value = fields.Date.to_date(text)
    except (ValueError, TypeError):
        value = None
    if not value:
        raise NotFound()
    return value


def _default_monday(today):
    """The week the week page opens on: this week, or next week on a weekend (what's coming up)."""
    monday = today - timedelta(days=today.weekday())
    return monday + timedelta(days=7) if today.weekday() >= 5 else monday


def _parse_iso_week(label):
    """'2026-W10' -> the Monday of that ISO week."""
    try:
        year, week = label.split("-W")
        return date.fromisocalendar(int(year), int(week), 1)
    except (ValueError, AttributeError):
        raise NotFound()


class HomeschoolPortal(PortalKitDashboard):

    # ------------------------------------------------------------------
    # who may see which student
    # ------------------------------------------------------------------
    def _portal_student_domain(self):
        uid = request.env.user.id
        return ["|", ("user_id", "=", uid), ("resource_user_ids", "in", [uid])]

    def _portal_students(self):
        """The students the user may see: his own, or the ones he follows as a resource
        user — searched as the user (the core's portal rule on ``homeschool.student``
        says the same thing; the domain here keeps the pages explicit). A user with no
        read access on students at all (an internal user outside the homeschool groups,
        on an instance where other apps share the portal) simply sees none: the portal
        home must never fail for him."""
        Student = request.env["homeschool.student"]
        if not Student.has_access("read"):
            return Student.browse()
        return Student.search(self._portal_student_domain(), order="name, id")

    def _portal_student(self, student_id):
        Student = request.env["homeschool.student"]
        if not Student.has_access("read"):
            raise NotFound()
        student = Student.search([("id", "=", student_id)] + self._portal_student_domain(), limit=1)
        if not student:
            raise NotFound()
        return student

    def _portal_role(self, student):
        """'student' for the student's own login, 'resource' for an attached teacher."""
        return "student" if student.user_id == request.env.user else "resource"

    def _homeschool_values(self, student, page_name):
        values = self._prepare_portal_layout_values()
        values.update({
            "student": student,
            "role": self._portal_role(student),
            "homeschool_role": self._portal_role(student),
            "page_name": page_name,
            "base_url": "/my/homeschool/%d" % student.id,
            "today": fields.Date.context_today(request.env.user),
        })
        request.session[SESSION_STUDENT] = student.id
        return values

    # ------------------------------------------------------------------
    # the app (Bemade portal kit): shell or stock portal, the learner switcher
    # ------------------------------------------------------------------
    @staticmethod
    def _hs_in_app():
        """Is the current request served in the homeschool app (``HS_APP``)?"""
        return request.env["portal.kit"]._pk_current_app() == HS_APP

    def _hs_shell_on(self):
        """The kit's switch is on and the user is in the homeschool app."""
        return bool(self._pk_shell_active() and self._hs_in_app())

    def _hs_current_student(self, students=None):
        """The learner the user is looking at, for the pages whose URL names none
        (« Today », the nav entries): ``?student_id=`` when it is one of his, else the
        last one he looked at (session), else his own student, else the first one he
        follows. Empty when he sees no student."""
        students = self._portal_students() if students is None else students
        if not students:
            return students
        wanted = request.params.get("student_id")
        try:
            wanted = int(wanted) if wanted else None
        except (TypeError, ValueError):
            wanted = None
        if wanted not in students.ids:
            wanted = request.session.get(SESSION_STUDENT)
        if wanted in students.ids:
            student = students.browse(wanted)
        else:
            own = students.filtered(lambda s: s.user_id == request.env.user)
            student = (own or students)[:1]
        request.session[SESSION_STUDENT] = student.id
        return student

    @staticmethod
    def _hs_switch_url(student):
        """The current page for another learner: the same section of a student URL
        (``/my/homeschool/<id>/<section>…``, cut before the first record id: a trace or
        a book belongs to one learner), else the current path with ``?student_id=``."""
        path = request.httprequest.path
        parts = path.strip("/").split("/")
        if len(parts) >= 3 and parts[:2] == ["my", "homeschool"] and parts[2].isdigit():
            tail = []
            for part in parts[3:]:
                if part.isdigit():
                    break
                tail.append(part)
            return "/".join(["/my/homeschool/%d" % student.id] + tail)
        return "%s?student_id=%d" % (path, student.id)

    def _hs_role_label(self, roles):
        env = request.env
        labels = []
        if HS_LEARNER in roles:
            labels.append(env._("Learner"))
        if HS_TUTOR in roles:
            labels.append(env._("Tutor"))
        return " · ".join(labels)

    def _hs_shell_values(self, values, page=None, student=None):
        """``values`` + the shell's (``PortalKitShell._pk_shell_values``) + the
        homeschool ones: the role in the user menu, the learner switcher (a tutor with
        more than one learner) and the home of the app."""
        user = request.env.user
        students = self._portal_students()
        student = student or values.get("student") or self._hs_current_student(students)
        switcher = []
        if len(students) > 1:
            switcher = [{
                "id": s.id, "name": s.name or "", "url": self._hs_switch_url(s), "active": s == student,
            } for s in students]
        extra = {
            # Every lookup of a homeschool page in the homeschool app.
            "pk_app_key": HS_APP,
            "pk_user_role": self._hs_role_label(hs_user_roles(user)),
            "pk_home_url": HS_HOME_URL,
            "hs_switcher": switcher,
            "hs_current_student": student,
        }
        return self._pk_shell_values(values, page, extra)

    def _pk_app_values(self, values, page=None):
        """The kit's own pages (settings, More, account…) in the homeschool app carry
        the homeschool values too; any other app's are its own."""
        if not self._hs_in_app():
            return super()._pk_app_values(values, page)
        return self._hs_shell_values(values, page)

    def _hs_render(self, template, values, page_key, title=None, active_nav=None):
        """A homeschool page: in the kit's shell when it is on for the user (the page's
        template draws itself on ``hs_layout``), else on the stock portal layout."""
        if not self._hs_shell_on():
            values["hs_layout"] = STOCK_LAYOUT
            return request.render(template, values)
        values.update({
            "hs_layout": HS_LAYOUT,
            "pk_title": title or "",
            "pk_active_nav": active_nav,
        })
        return self._pk_render(template, self._hs_shell_values(values, "homeschool_portal.%s" % page_key))

    @http.route(["/my/homeschool/<any(%s):section>" % ",".join(SECTIONS)],
                type="http", auth="user", website=True)
    def portal_homeschool_section(self, section, **kw):
        """A nav entry: the section of the learner the user is looking at."""
        student = self._hs_current_student()
        if not student:
            return request.redirect("/my/homeschool")
        return request.redirect("/my/homeschool/%d/%s" % (student.id, section))

    # ------------------------------------------------------------------
    # « Today »: the kit's dashboard (bemade_portal_kit_dashboard)
    # ------------------------------------------------------------------
    def _hs_dash_render(self, values):
        """« Today »: the homeschool app's home (``home_render`` of its registration,
        ``models/portal_kit.py``), called by the kit's ``/my/home`` for a user of the
        homeschool app."""
        if not values.get("hs_student"):
            today = fields.Date.context_today(request.env.user)
            values.update({
                "hs_student": self._hs_current_student(),
                "hs_today": today,
                "hs_today_label": format_date(request.env, today, date_format="EEEE d MMMM"),
            })
        student = values.get("hs_student")
        if self._hs_learner_only():
            values["pk_dash_configure_url"] = False  # the learner's Today is set up for him
        values.update({
            "pk_title": request.env._("Today"),
            "pk_active_nav": "hs_today",
            "hs_layout": HS_LAYOUT,
        })
        return self._pk_render("homeschool_portal.hs_dash_page",
                               self._hs_shell_values(values, "homeschool_portal.hs_dash_page", student=student))

    def _hs_learner_only(self):
        roles = hs_user_roles(request.env.user)
        return HS_LEARNER in roles and HS_TUTOR not in roles

    @http.route()
    def pk_dash_configure(self, **kw):
        if self._hs_in_app() and self._hs_learner_only():
            return request.redirect(HS_HOME_URL)
        return super().pk_dash_configure(**kw)

    def _pk_dash_context(self, Dash, viewer):
        ctx = super()._pk_dash_context(Dash, viewer)
        if viewer.get("app") != HS_APP:
            return ctx
        student = self._hs_current_student()
        today = fields.Date.context_today(request.env.user)
        ctx.update({
            "hs_student": student,
            "hs_role": self._portal_role(student) if student else False,
            "hs_today": today,
            "hs_base_url": "/my/homeschool/%d" % student.id if student else "",
        })
        return ctx

    def _pk_dash_page_values(self, values, ctx):
        values = super()._pk_dash_page_values(values, ctx)
        if ctx["viewer"].get("app") == HS_APP and ctx.get("hs_student") is not None:
            values.update({
                "hs_student": ctx["hs_student"],
                "hs_today": ctx["hs_today"],
                "hs_today_label": format_date(request.env, ctx["hs_today"], date_format="EEEE d MMMM"),
            })
        return values

    def _hs_dash_day(self, ctx):
        student = ctx.get("hs_student")
        if not student:
            return request.env["homeschool.day"]
        return request.env["homeschool.day"].search(
            [("student_id", "=", student.id), ("date", "=", ctx["hs_today"])], limit=1)

    def _hs_dash_list(self, instance, scope, ctx):
        """Today's list: its lines, tick-boxes for the learner himself (the day page's
        tick route, back here)."""
        day = self._hs_dash_day(ctx)
        Deliverable = request.env["homeschool.deliverable"]
        lines = Deliverable.search([("day_id", "=", day.id)], order="sequence, id") if day else Deliverable
        base = ctx.get("hs_base_url")
        return {
            "hs_lines": lines,
            "hs_can_tick": ctx.get("hs_role") == "student",
            "hs_base_url": base,
            "hs_return_url": "%s?student_id=%d" % (HS_HOME_URL, ctx["hs_student"].id) if base else HS_HOME_URL,
            "hs_done_count": len(lines.filtered("done")),
            "list_url": "%s/day" % base if base else False,
        }

    def _hs_dash_blocks(self, instance, scope, ctx):
        """Today's blocks, in sequence (kind, times, name)."""
        day = self._hs_dash_day(ctx)
        Block = request.env["homeschool.block"]
        blocks = Block.search([("day_id", "=", day.id)], order="sequence, id") if day else Block
        base = ctx.get("hs_base_url")
        return {
            "hs_day": day,
            "hs_blocks": blocks,
            "hs_kind_labels": self._kind_labels(),
            "hs_fmt_hour": _fmt_hour,
            "list_url": "%s/day" % base if base else False,
        }

    def _hs_dash_reading(self, instance, scope, ctx):
        """Today's reading entry: written or still to write, per book in progress."""
        student = ctx.get("hs_student")
        Book = request.env["homeschool.reading.book"]
        books = Book.search([("student_id", "=", student.id), ("finished", "=", False)]) if student else Book
        Entry = request.env["homeschool.reading.entry"]
        written = Entry.search([("book_id", "in", books.ids), ("date", "=", ctx["hs_today"])]) if books else Entry
        base = ctx.get("hs_base_url")
        return {
            "hs_books": [{"book": b, "done": b in written.book_id, "url": "%s/reading/%d" % (base, b.id)}
                         for b in books],
            "list_url": "%s/reading" % base if base else False,
        }

    @staticmethod
    def _kind_labels():
        """The block kinds as the core names them, in the user's language."""
        env = request.env
        return dict(env["homeschool.block"]._fields["kind"]._description_selection(env))

    def _attachment_rows(self, record, field="attachment_ids"):
        """Name and size of the files of a trace or a material the user can read, read as
        the user: the core stamps every linked file with its record, so a file follows
        the access of its trace or material."""
        env = request.env
        return [
            {
                "id": att.id, "name": att.name, "mimetype": att.mimetype, "size": att.file_size,
                "size_label": env._("(%(kb).1f KB)", kb=att.file_size / 1024.0) if att.file_size else "",
            }
            for att in record[field]
        ]

    # ------------------------------------------------------------------
    # portal home
    # ------------------------------------------------------------------
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if "homeschool_student_count" in counters:
            values["homeschool_student_count"] = len(self._portal_students())
        if not counters:
            # page render only (never the /my/counters JSON): the card's wording
            students = self._portal_students()
            values["homeschool_portal_role"] = (
                "student" if any(s.user_id == request.env.user for s in students) else "resource"
            )
        return values

    @http.route(["/my/homeschool"], type="http", auth="user", website=True)
    def portal_homeschool_home(self, **kw):
        students = self._portal_students()
        values = self._prepare_portal_layout_values()
        roles = {s.id: self._portal_role(s) for s in students}
        values.update({
            "students": students,
            "roles": roles,
            "homeschool_role": "student" if "student" in roles.values() else "resource",
            "page_name": "homeschool_home",
        })
        return self._hs_render("homeschool_portal.portal_home", values, "hs_home",
                               title=request.env._("Learners"), active_nav="hs_today")

    # ------------------------------------------------------------------
    # day
    # ------------------------------------------------------------------
    @http.route([
        "/my/homeschool/<int:student_id>",
        "/my/homeschool/<int:student_id>/day",
        "/my/homeschool/<int:student_id>/day/<string:date_str>",
    ], type="http", auth="user", website=True)
    def portal_homeschool_day(self, student_id, date_str=None, **kw):
        student = self._portal_student(student_id)
        day_date = _parse_date(date_str) if date_str else fields.Date.context_today(request.env.user)
        Day = request.env["homeschool.day"]
        Block = request.env["homeschool.block"]
        Deliverable = request.env["homeschool.deliverable"]
        Material = request.env["homeschool.material"]
        day = Day.search([("student_id", "=", student.id), ("date", "=", day_date)], limit=1)
        prev_day = Day.search([("student_id", "=", student.id), ("date", "<", day_date)], order="date desc", limit=1)
        next_day = Day.search([("student_id", "=", student.id), ("date", ">", day_date)], order="date asc", limit=1)
        blocks = Block.search([("day_id", "=", day.id)], order="sequence, id") if day else Block
        deliverables = Deliverable.search([("day_id", "=", day.id)], order="sequence, id") if day else Deliverable
        # searched as the user: only institutional material of the family comes back
        materials = Material.search([("block_ids", "in", blocks.ids)], order="name") if blocks else Material
        values = self._homeschool_values(student, "homeschool_day")
        values.update({
            "day": day,
            "day_date": day_date,
            "prev_day": prev_day,
            "next_day": next_day,
            "blocks": blocks,
            "deliverables": deliverables,
            "materials": materials,
            "material_files": {m.id: self._attachment_rows(m) for m in materials},
            "kind_labels": self._kind_labels(),
            "fmt_hour": _fmt_hour,
            "iso_week": iso_week_label(day_date),
            "ticked": kw.get("ticked"),
        })
        return self._hs_render("homeschool_portal.portal_day", values, "hs_day",
                               title=format_date(request.env, day_date, date_format="EEEE d MMMM"),
                               active_nav="hs_today")

    @http.route(
        ["/my/homeschool/<int:student_id>/deliverable/<int:deliverable_id>/tick"],
        type="http", auth="user", methods=["POST"], website=True,
    )
    def portal_homeschool_tick(self, student_id, deliverable_id, done="1", return_url=None, **kw):
        """The student ticks (or unticks) one line of his list. The write runs as the
        user: the core rule (own student only) and the model guard (``done`` only) apply;
        a resource user is refused here already. From « Today »'s card (``return_url``,
        a same-site ``/my/`` path) he goes back there with a toast; else to the day."""
        student = self._portal_student(student_id)
        if self._portal_role(student) != "student":
            raise Forbidden()
        deliverable = request.env["homeschool.deliverable"].search(
            [("id", "=", deliverable_id), ("student_id", "=", student.id)], limit=1
        )
        if not deliverable:
            raise NotFound()
        deliverable.write({"done": done == "1"})
        back = pk_safe_return_url(return_url, None, prefixes=("/my/",))
        if back:
            request.session["notification"] = {
                "type": "success", "title": "",
                "message": request.env._("Ticked off.") if done == "1" else request.env._("Unticked."),
            }
            return request.redirect(back)
        return request.redirect("/my/homeschool/%d/day/%s?ticked=%d" % (student.id, deliverable.date, deliverable.id))

    # ------------------------------------------------------------------
    # week
    # ------------------------------------------------------------------
    @http.route([
        "/my/homeschool/<int:student_id>/week",
        "/my/homeschool/<int:student_id>/week/<string:iso_week>",
    ], type="http", auth="user", website=True)
    def portal_homeschool_week(self, student_id, iso_week=None, **kw):
        student = self._portal_student(student_id)
        today = fields.Date.context_today(request.env.user)
        monday = _parse_iso_week(iso_week) if iso_week else _default_monday(today)
        Day = request.env["homeschool.day"]
        Block = request.env["homeschool.block"]
        days = Day.search([
            ("student_id", "=", student.id),
            ("date", ">=", monday), ("date", "<=", monday + timedelta(days=6)),
        ])
        blocks = Block.search([("day_id", "in", days.ids)], order="day_id, sequence, id") if days else Block
        by_date = {d.date: d for d in days}
        blocks_by_day = {d.id: blocks.filtered(lambda b, d=d: b.day_id == d) for d in days}
        columns = []
        for offset in range(7):
            d = monday + timedelta(days=offset)
            day = by_date.get(d)
            if offset >= WEEK_DAYS and not day:
                continue  # weekends only when something is planned
            columns.append({"date": d, "day": day, "blocks": blocks_by_day.get(day.id, Block) if day else Block})
        values = self._homeschool_values(student, "homeschool_week")
        values.update({
            "monday": monday,
            "friday": monday + timedelta(days=WEEK_DAYS - 1),
            "iso_week": iso_week_label(monday),
            "prev_week": iso_week_label(monday - timedelta(days=7)),
            "next_week": iso_week_label(monday + timedelta(days=7)),
            "columns": columns,
            "kind_labels": self._kind_labels(),
            "fmt_hour": _fmt_hour,
        })
        return self._hs_render("homeschool_portal.portal_week", values, "hs_week",
                               title=request.env._("Week %(week)s", week=values["iso_week"]), active_nav="hs_week")

    # ------------------------------------------------------------------
    # traces
    # ------------------------------------------------------------------
    @http.route([
        "/my/homeschool/<int:student_id>/traces",
        "/my/homeschool/<int:student_id>/traces/page/<int:page>",
    ], type="http", auth="user", website=True)
    def portal_homeschool_traces(self, student_id, page=1, **kw):
        student = self._portal_student(student_id)
        Trace = request.env["homeschool.trace"]
        # as the user: institutional traces of the family + the user's own pending ones
        domain = [("student_id", "=", student.id)]
        pager = portal_pager(
            url="/my/homeschool/%d/traces" % student.id,
            total=Trace.search_count(domain), page=page, step=self._items_per_page,
        )
        traces = Trace.search(domain, order="date desc, code desc", limit=self._items_per_page, offset=pager["offset"])
        values = self._homeschool_values(student, "homeschool_traces")
        values.update({"traces": traces, "pager": pager})
        return self._hs_render("homeschool_portal.portal_traces", values, "hs_traces",
                               title=request.env._("Traces"), active_nav="hs_traces")

    def _portal_trace(self, student, trace_id):
        trace = request.env["homeschool.trace"].search(
            [("id", "=", trace_id), ("student_id", "=", student.id)], limit=1
        )
        if not trace:
            raise NotFound()
        return trace

    @http.route(["/my/homeschool/<int:student_id>/traces/<int:trace_id>"], type="http", auth="user", website=True)
    def portal_homeschool_trace(self, student_id, trace_id, **kw):
        student = self._portal_student(student_id)
        trace = self._portal_trace(student, trace_id)
        values = self._homeschool_values(student, "homeschool_trace")
        values.update({
            "trace": trace,
            "object": trace,  # portal.message_thread
            "attachments": self._attachment_rows(trace),
            "submitted": kw.get("submitted"),
        })
        return self._hs_render("homeschool_portal.portal_trace", values, "hs_trace",
                               title=trace.name, active_nav="hs_traces")

    @http.route(
        ["/my/homeschool/<int:student_id>/traces/submit"],
        type="http", auth="user", methods=["GET", "POST"], website=True,
    )
    def portal_homeschool_submit(self, student_id, **post):
        """Hand a trace in. The trace is created as the user: the core guard stores it
        ``internal``, not validated, ``submitted_by`` = the user's relation to the
        student. Files are attached afterwards (see ``_attach_submitted_files``)."""
        student = self._portal_student(student_id)
        values = self._homeschool_values(student, "homeschool_submit")
        values.update({
            "errors": [],
            "form": {"date": fields.Date.to_string(values["today"])},
            "files_hint": request.env._(
                "Photos, PDF, audio… %(files)s files and %(mb)s MB in all at most.", files=MAX_FILES, mb=MAX_TOTAL_MB,
            ),
        })
        if request.httprequest.method == "POST":
            form = {
                "name": (post.get("name") or "").strip(),
                "date": (post.get("date") or "").strip(),
                "student_comment": (post.get("student_comment") or "").strip(),
            }
            values["form"] = form
            uploads = [f for f in request.httprequest.files.getlist("files") if f and f.filename]
            errors = self._validate_submission(form, uploads)
            if errors:
                values["errors"] = errors
            else:
                trace = request.env["homeschool.trace"].create({
                    "name": form["name"],
                    "date": form["date"],
                    "student_id": student.id,
                    "student_comment": form["student_comment"] or False,
                })
                self._attach_submitted_files(trace, uploads)
                return request.redirect("/my/homeschool/%d/traces/%d?submitted=1" % (student.id, trace.id))
        return self._hs_render("homeschool_portal.portal_submit", values, "hs_submit",
                               title=request.env._("Hand in a trace"), active_nav="hs_traces")

    def _validate_submission(self, form, uploads):
        env = request.env
        errors = []
        if not form["name"]:
            errors.append(env._("Give your trace a title."))
        try:
            if not fields.Date.to_date(form["date"]):
                raise ValueError()
        except (ValueError, TypeError):
            errors.append(env._("The date is not valid."))
        if len(uploads) > MAX_FILES:
            errors.append(env._("You may attach at most %(count)s files.", count=MAX_FILES))
        total = 0
        for upload in uploads:
            upload.stream.seek(0, 2)
            total += upload.stream.tell()
            upload.stream.seek(0)
        if total > MAX_TOTAL_MB * 1024 * 1024:
            errors.append(env._("The files are too big: %(size)s MB in all at most.", size=MAX_TOTAL_MB))
        return errors

    def _attach_submitted_files(self, trace, uploads):
        """Attach the uploaded files to the trace the user has just created — as the user:
        he may write his own pending trace (core rule), so he may create attachments on it
        and link them (Odoo's attachment access follows the record's write access)."""
        if not uploads:
            return
        if trace.create_uid != request.env.user or trace.validated:
            raise Forbidden()
        attachments = request.env["ir.attachment"].create([{
            "name": secure_filename(upload.filename) or "file",
            "raw": upload.read(),
            "res_model": "homeschool.trace",
            "res_id": trace.id,
        } for upload in uploads])
        trace.write({"attachment_ids": [Command.link(att.id) for att in attachments]})

    # ------------------------------------------------------------------
    # files of traces and material
    # ------------------------------------------------------------------
    def _attachment_reachable(self, student, attachment_id):
        """As the user (the record rules decide): is the file carried by a trace of this
        student, or by material of his family, that the user can read?"""
        Trace = request.env["homeschool.trace"]
        if Trace.search_count([("student_id", "=", student.id), ("attachment_ids", "in", [attachment_id])]):
            return True
        Material = request.env["homeschool.material"]
        return bool(Material.search_count([
            ("company_id", "=", student.company_id.id),
            "|", ("pdf_attachment_id", "=", attachment_id), ("attachment_ids", "in", [attachment_id]),
        ]))

    @http.route(["/my/homeschool/<int:student_id>/file/<int:attachment_id>"], type="http", auth="user", website=True)
    def portal_homeschool_file(self, student_id, attachment_id, **kw):
        """Serve a file of a readable trace or material, always as a download (never
        rendered inline, whatever its type)."""
        student = self._portal_student(student_id)
        if not self._attachment_reachable(student, attachment_id):
            raise NotFound()
        attachment = request.env["ir.attachment"].browse(attachment_id).exists()
        if not attachment:
            raise NotFound()
        try:
            stream = request.env["ir.binary"]._get_stream_from(attachment, "raw")
        except AccessError:
            # a file the core has not stamped with its record (never after 19.0.5.0.0)
            raise NotFound()
        return stream.get_response(as_attachment=True)

    # ------------------------------------------------------------------
    # reading log
    # ------------------------------------------------------------------
    @http.route(["/my/homeschool/<int:student_id>/reading"], type="http", auth="user", website=True)
    def portal_homeschool_reading(self, student_id, **kw):
        student = self._portal_student(student_id)
        books = request.env["homeschool.reading.book"].search([("student_id", "=", student.id)])
        values = self._homeschool_values(student, "homeschool_reading")
        values.update({"books": books})
        return self._hs_render("homeschool_portal.portal_reading", values, "hs_reading",
                               title=request.env._("Reading log"), active_nav="hs_reading")

    def _portal_book(self, student, book_id):
        book = request.env["homeschool.reading.book"].search(
            [("id", "=", book_id), ("student_id", "=", student.id)], limit=1
        )
        if not book:
            raise NotFound()
        return book

    @http.route(["/my/homeschool/<int:student_id>/reading/<int:book_id>"], type="http", auth="user", website=True)
    def portal_homeschool_book(self, student_id, book_id, **kw):
        student = self._portal_student(student_id)
        book = self._portal_book(student, book_id)
        entries = request.env["homeschool.reading.entry"].search([("book_id", "=", book.id)], order="date desc, id desc")
        values = self._homeschool_values(student, "homeschool_book")
        form_date = values["today"]
        if kw.get("date"):
            form_date = _parse_date(kw["date"])
        current = entries.filtered(lambda e: e.date == form_date)[:1]
        values.update({
            "book": book,
            "entries": entries,
            "form_date": form_date,
            "current": current,
            "is_friday": form_date.weekday() == 4,
            "saved": kw.get("saved"),
        })
        return self._hs_render("homeschool_portal.portal_book", values, "hs_book",
                               title=book.title, active_nav="hs_reading")

    @http.route(
        ["/my/homeschool/<int:student_id>/reading/<int:book_id>/entry"],
        type="http", auth="user", methods=["POST"], website=True,
    )
    def portal_homeschool_entry(self, student_id, book_id, **post):
        """The student writes (or completes) the entry of one day. Create and write run
        as the user: the core rule (own student) and guard (``written_by`` is himself)."""
        student = self._portal_student(student_id)
        if self._portal_role(student) != "student":
            raise Forbidden()
        book = self._portal_book(student, book_id)
        entry_date = _parse_date(post.get("date"))
        Entry = request.env["homeschool.reading.entry"]
        vals = {key: (post.get(key) or "").strip() or False for key in ("word1", "word2", "question", "answer", "weekly_page")}
        entry = Entry.search([("book_id", "=", book.id), ("date", "=", entry_date)], limit=1)
        if entry:
            entry.write(vals)
        else:
            Entry.create(dict(vals, book_id=book.id, date=entry_date))
        return request.redirect("/my/homeschool/%d/reading/%d?date=%s&saved=1" % (student.id, book.id, entry_date))
