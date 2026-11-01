# -*- coding: utf-8 -*-
"""UC-20 — Blocks: « This week » right on every weekday, « Next week », and the board's
day columns from the oldest to the newest.

Acceptance criteria
-------------------
1. The « This week » filter of the Blocks search view covers **Monday → Sunday of the
   current week whatever the day it is opened** — a Monday included (it used to show the
   whole of last week), a Sunday included (the week is still there when it is closed).
   Lower bound = that week's Monday, upper bound (exclusive) = the following Monday.
2. A « Next week » filter covers Monday → Sunday of the following week. It sits right
   after « This week » **in the same filter group** (no separator between them), so
   ticking both shows the two weeks; it is not a default — ``search_default_this_week``
   stays the only default of the Blocks action.
3. Both hold across a year boundary (the week Mon 2026-12-28 → Sun 2027-01-03).
4. The Blocks board (kanban grouped by day) asks for ``day_id desc, sequence``: the
   grouped read then returns the day columns in **chronological** order (the ORM orders a
   many2one group by the comodel ``_order`` — ``date desc`` for a day — and reverses it
   when the direction is DESC), and the cards of a column keep their ``sequence``.
5. Nothing else moves: ``homeschool.day`` keeps ``_order = "date desc"`` (day pickers list
   the most recent day first), the Blocks list keeps ``date desc, sequence``, and the same
   order string is accepted by the server when the board is grouped by subject or by kind.

The view domains are evaluated by the web client (py.js); these tests evaluate the very
same strings with ``dateutil``. What the browser does with them is checked by hand.
"""
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta
from lxml import etree

from odoo.fields import Domain
from odoo.tools.safe_eval import safe_eval

from .common import HomeschoolCase

# The Mondays of the two probed weeks: an ordinary one, and the one straddling the year.
PROBE_MONDAYS = (date(2026, 10, 5), date(2026, 12, 28))
KANBAN_ORDER = "day_id desc, sequence"


class TestBlockWeekFilters(HomeschoolCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.search_arch = etree.fromstring(cls.env.ref("homeschool.view_block_search").arch)
        cls.kanban_arch = etree.fromstring(cls.env.ref("homeschool.view_block_kanban").arch)

    # helpers -----------------------------------------------------------
    def _filter(self, name):
        nodes = self.search_arch.xpath("//filter[@name='%s']" % name)
        self.assertEqual(len(nodes), 1, "the Blocks search view has exactly one %r filter" % name)
        return nodes[0]

    def _domain(self, name, today):
        """The filter's domain as the client would get it on ``today``."""
        return safe_eval(self._filter(name).get("domain"), {
            "context_today": lambda: today,
            "relativedelta": relativedelta,
        })

    def _bounds(self, name, today):
        domain = self._domain(name, today)
        self.assertEqual(len(domain), 2, domain)
        (lfield, lop, lower), (ufield, uop, upper) = domain
        self.assertEqual((lfield, lop, ufield, uop), ("date", ">=", "date", "<"), domain)
        return date.fromisoformat(lower), date.fromisoformat(upper)

    def _probes(self):
        for monday in PROBE_MONDAYS:
            for offset in range(7):
                yield monday, monday + timedelta(days=offset)

    def _week_of_blocks(self, first_monday, weeks=4):
        """One block a day over ``weeks`` weeks starting on ``first_monday`` (created
        newest first, so nothing rides on the creation order)."""
        blocks = self.Block
        for offset in reversed(range(7 * weeks)):
            d = first_monday + timedelta(days=offset)
            blocks |= self.make_block(self.make_day(d), "Block %s" % d.isoformat(), 30, 1, subject_id=self.math.id)
        return blocks

    # the two filters ---------------------------------------------------
    def test_this_week_monday_to_sunday(self):
        for monday, today in self._probes():
            with self.subTest(today=today.isoformat(), weekday=today.strftime("%a")):
                self.assertEqual(self._bounds("this_week", today), (monday, monday + timedelta(days=7)))

    def test_next_week_monday_to_sunday(self):
        for monday, today in self._probes():
            with self.subTest(today=today.isoformat(), weekday=today.strftime("%a")):
                self.assertEqual(
                    self._bounds("next_week", today),
                    (monday + timedelta(days=7), monday + timedelta(days=14)),
                )

    def test_filters_share_a_group(self):
        this_week = self._filter("this_week")
        next_week = self._filter("next_week")
        # element siblings only ("*"): an XML comment between two filters does not split a group
        self.assertEqual(this_week.xpath("following-sibling::*[1]"), [next_week],
                         "« Next week » comes right after « This week », no separator")
        self.assertEqual(this_week.get("string"), "This week")
        self.assertEqual(next_week.get("string"), "Next week")
        self.assertEqual([n.tag for n in this_week.xpath("preceding-sibling::*[1]")], ["separator"],
                         "the two week filters are a group of their own")
        self.assertNotEqual([n.tag for n in next_week.xpath("following-sibling::*[1]")], ["filter"],
                            "nothing else joins the week filters' group")
        # « This week » stays the one and only default of the Blocks action
        context = safe_eval(self.env.ref("homeschool.action_block").context)
        self.assertEqual({k: v for k, v in context.items() if k.startswith("search_default_")}, {"search_default_this_week": 1})

    def test_filters_select_the_right_blocks(self):
        """The evaluated domains against real blocks: last week, this week, next week and
        the week after, opened on the Monday and on the Sunday of « this week »."""
        last_monday = PROBE_MONDAYS[0] - timedelta(days=7)
        blocks = self._week_of_blocks(last_monday)
        monday = PROBE_MONDAYS[0]

        def dates(domain):
            return sorted(self.Block.search(Domain("id", "in", blocks.ids) & Domain(domain)).mapped("date"))

        def week(start):
            return [start + timedelta(days=i) for i in range(7)]

        for today in (monday, monday + timedelta(days=6)):
            with self.subTest(today=today.isoformat()):
                this_week = self._domain("this_week", today)
                next_week = self._domain("next_week", today)
                self.assertEqual(dates(this_week), week(monday))
                self.assertEqual(dates(next_week), week(monday + timedelta(days=7)))
                # both ticked: filters of one group are OR-ed by the search view
                self.assertEqual(dates(Domain.OR([this_week, next_week])), week(monday) + week(monday + timedelta(days=7)))

    # the board's columns -----------------------------------------------
    def _three_days(self):
        """Three non-consecutive days created out of order, two blocks on the middle one."""
        middle = self.make_day(date(2026, 10, 7))
        newest = self.make_day(date(2026, 10, 16))
        oldest = self.make_day(date(2026, 9, 29))
        blocks = self.make_block(newest, "Newest", 30, 1, subject_id=self.fle.id)
        blocks |= self.make_block(middle, "Middle second", 30, 2, subject_id=self.math.id, kind="reading")
        blocks |= self.make_block(oldest, "Oldest", 30, 1, subject_id=self.math.id)
        blocks |= self.make_block(middle, "Middle first", 30, 1, subject_id=self.fle.id)
        return oldest, middle, newest, blocks

    def _board(self, blocks, groupby, order=None):
        """The grouped read of the web client's kanban (``web_read_group``, groups unfolded)."""
        return self.Block.web_read_group(
            [("id", "in", blocks.ids)], [groupby], order=order, auto_unfold=True,
            unfold_read_specification={"name": {}, "sequence": {}, "date": {}},
        )["groups"]

    def test_kanban_day_columns_chronological(self):
        self.assertEqual(self.kanban_arch.get("default_group_by"), "day_id")
        self.assertEqual(self.kanban_arch.get("default_order"), KANBAN_ORDER)

        oldest, middle, newest, blocks = self._three_days()
        groups = self._board(blocks, "day_id", KANBAN_ORDER)
        self.assertEqual([g["day_id"][0] for g in groups], [oldest.id, middle.id, newest.id])
        # inside a column the cards keep their sequence
        self.assertEqual([r["name"] for r in groups[1]["__records"]], ["Middle first", "Middle second"])
        # the bare group order alone gives the same columns
        groups = self._board(blocks, "day_id", "day_id desc")
        self.assertEqual([g["day_id"][0] for g in groups], [oldest.id, middle.id, newest.id])

    def test_day_order_untouched(self):
        """The model order is what it was: without the view's order the newest day comes
        first, and so it does in a day picker."""
        oldest, middle, newest, blocks = self._three_days()
        self.assertEqual(self.Day._order, "date desc")
        groups = self._board(blocks, "day_id")
        self.assertEqual([g["day_id"][0] for g in groups], [newest.id, middle.id, oldest.id])
        days = oldest | middle | newest
        self.assertEqual(self.Day.search([("id", "in", days.ids)]).ids, [newest.id, middle.id, oldest.id])
        picked = [res_id for res_id, _name in self.Day.name_search("", [("id", "in", days.ids)])]
        self.assertEqual(picked, [newest.id, middle.id, oldest.id])
        # the Blocks list view keeps its own order
        list_arch = etree.fromstring(self.env.ref("homeschool.view_block_list").arch)
        self.assertEqual(list_arch.get("default_order"), "date desc, sequence")

    def test_kanban_order_tolerated_by_other_groupings(self):
        """Grouped by subject or by kind, the board sends the same order string: the server
        accepts it (``day_id`` is then not a group-by), keeps the groups in their own
        order, and sorts the cards of a column by day (chronological) then sequence."""
        oldest, middle, newest, blocks = self._three_days()

        by_subject = self._board(blocks, "subject_id", KANBAN_ORDER)
        self.assertEqual([g["subject_id"][0] for g in by_subject],
                         [g["subject_id"][0] for g in self._board(blocks, "subject_id")])
        self.assertEqual({g["subject_id"][0]: [r["name"] for r in g["__records"]] for g in by_subject}, {
            self.math.id: ["Oldest", "Middle second"],
            self.fle.id: ["Middle first", "Newest"],
        })

        by_kind = self._board(blocks, "kind", KANBAN_ORDER)
        self.assertEqual([g["kind"] for g in by_kind], [g["kind"] for g in self._board(blocks, "kind")])
        self.assertEqual({g["kind"]: [r["name"] for r in g["__records"]] for g in by_kind}, {
            "bloc": ["Oldest", "Middle first", "Newest"],
            "reading": ["Middle second"],
        })
