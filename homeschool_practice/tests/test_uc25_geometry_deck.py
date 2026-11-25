# -*- coding: utf-8 -*-
"""UC-25 — A geometry practice set with drawn figures (Québec PDA, grades 5–6).

Acceptance criteria
-------------------
1. « Load math practice decks » (``deck.action_load_math()``, managers only) also loads
   « La géométrie » (subject Mathematics), from ``data/math_geometry_units.csv`` and
   ``_cards.csv``, through the same loader. Idempotent. Six units in teaching order: figures
   planes et polygones, les triangles, les quadrilatères, le cercle, les angles et les
   droites, les solides.
2. Each unit has an intro (the key words, one example each), a short hint and 12 to 16
   cards, easiest first. A choices card has 2 to 4 distinct options, exactly one correct;
   a keypad card's answer is digits only. Each unit lists its PDA curriculum items (codes
   absent from the database are skipped).
3. Teach first: every unit stays locked until a parent unlocks it.
4. A card can show a drawn figure. The cards CSV has an optional ``figure`` column: a figure
   spec (``tri kind=isosceles rot=20``) that the loader stores on the item
   (``figure_spec``) and turns into an SVG document (``figure``). Cards CSV without that
   column load as before, with no figure. Every geometry unit has figure cards.
5. Every figure is a safe, standalone SVG: valid XML, an ``<svg>`` root with a viewBox,
   drawing elements only, no script, event handler (``on…``), foreignObject, link (``href``)
   or ``url(…)``. An item refuses an unsafe figure (constraint), whoever writes it.
6. Every fact is checked against the drawing it sits on: counts of sides / vertices,
   polygon or not, convex or not, polygon names, triangle and quadrilateral names from the
   measured sides and angles (the distractors are false for that figure), the part of the
   circle marked, angle and line kinds, the solid's name and its faces / edges / vertices
   (from the drawn model, checked against a table and Euler's formula). Radius / diameter
   keypad answers are computed again from the prompt.
7. Position and orientation are not the cue: the same kind of figure appears in several
   sizes and orientations (a square tilted 45° among them).
8. The API item payload carries the figure only as data: ``figure`` is a
   ``data:image/svg+xml;base64,…`` URI of the stored SVG, an empty string for a card
   without one; the lesson screen shows it as an image (``<img>``), never as markup.
9. Synthetic content: no learner's name.
"""
import base64
import re

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import new_test_user, tagged
from odoo.tools.misc import mute_logger

from odoo.addons.homeschool_practice.models import figures

from .common import PracticeCase, PracticeHttpCase

DECK = "La géométrie"
UNITS = ["Figures planes et polygones", "Les triangles", "Les quadrilatères", "Le cercle",
         "Les angles et les droites", "Les solides"]
# faces, edges, vertices — an independent table (not the drawing model)
SOLID_TABLE = {"cube": (6, 12, 8), "box": (6, 12, 8), "prism3": (5, 9, 6), "prism6": (8, 18, 12),
               "pyramid4": (5, 8, 5), "pyramid3": (4, 6, 4)}
CIRCLE_PARTS = {"center": "le centre", "radius": "le rayon", "diameter": "le diamètre",
                "circumference": "la circonférence", "disk": "le disque", "angle": "un angle au centre"}
SOLID_WORDS = {"cube": "un cube", "cylindre": "un cylindre", "cône": "un cône", "boule": "une boule",
               "prisme": "un prisme", "pyramide": "une pyramide"}
UNSAFE = [
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><script>alert(1)</script></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" onload="alert(1)"/>',
    '<svg xmlns="http://www.w3.org/2000/svg" xmlns:x="http://www.w3.org/1999/xlink" viewBox="0 0 10 10">'
    '<image x:href="https://example.com/a.png"/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><foreignObject/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect fill="url(#x)"/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect',
    '<html/>',
]


def plain(text):
    return text.replace("\u00a0", " ")


def solid_word(name):
    return SOLID_WORDS[name.split(" ")[0]]


@tagged("post_install", "-at_install")
class TestGeometryDeck(PracticeCase):

    def setUp(self):
        super().setUp()
        self.ref = self.Item.create({"code": "MATH-GEO-C.8", "name": "triangles", "subject_id": self.math.id})
        self.Deck.action_load_math()
        self.geo = self.Deck.search([("name", "=", DECK)])

    def unit(self, name):
        return self.geo.unit_ids.filtered(lambda u: u.name == name)

    # 1-3 ------------------------------------------------------------------
    def test_deck_units_and_subject(self):
        self.assertEqual(len(self.geo), 1)
        self.assertEqual(self.geo.subject_id, self.math)
        self.assertEqual(self.geo.company_id, self.env.company)
        self.assertEqual(self.geo.unit_ids.sorted("sequence").mapped("name"), UNITS)
        self.assertFalse(self.geo.quest_daily)

    def test_cards(self):
        for unit in self.geo.unit_ids:
            self.assertTrue(unit.intro, unit.name)
            self.assertTrue(12 <= len(unit.item_ids) <= 16, unit.name)
            self.assertTrue(unit.item_ids.filtered("figure"), "%s has figure cards" % unit.name)
            for item in unit.item_ids:
                self.assertTrue(item.hint, item.key)
                if item.answer_mode == "keypad":
                    self.assertRegex(item.answer, r"^\d+$", item.key)
                    self.assertFalse(item.choice_ids, item.key)
                else:
                    self.assertTrue(2 <= len(item.choice_ids) <= 4, item.key)
                    self.assertEqual(len(item.choice_ids.filtered("correct")), 1, item.key)
                    self.assertEqual(item.answer, item.choice_ids.filtered("correct").label)
                    self.assertEqual(len(set(item.choice_ids.mapped("label"))), len(item.choice_ids), item.key)

    def test_idempotent(self):
        counts = (len(self.geo.unit_ids), len(self.geo.item_ids))
        self.Deck.action_load_math()
        self.assertEqual(self.Deck.search_count([("name", "=", DECK)]), 1)
        self.assertEqual((len(self.geo.unit_ids), len(self.geo.item_ids)), counts)

    def test_refs(self):
        self.assertEqual(self.unit("Les triangles").curriculum_item_ids, self.ref)

    def test_locked_until_taught(self):
        units = self.geo.unit_ids.sorted("sequence")
        self.assertFalse(units._unlocked_for(self.student))
        units[:4].action_unlock(self.student)
        self.assertEqual(units._unlocked_for(self.student), units[:4])
        session = self.Session._start(self.student, self.geo, kind="unit", unit=units[0])
        self.assertTrue(session._current_item())

    def test_managers_only(self):
        with self.assertRaises(AccessError):
            self.Deck.with_user(new_test_user(self.env, login="uc25_portal", groups="base.group_portal")
                                ).action_load_math()

    # 4-5 ------------------------------------------------------------------
    def test_figures_are_safe_svg(self):
        with_figure = self.geo.item_ids.filtered("figure")
        self.assertGreaterEqual(len(with_figure), 40)
        for item in with_figure:
            self.assertTrue(item.figure_spec, item.key)
            self.assertEqual(item.figure, figures.render(item.figure_spec), item.key)
            self.assertTrue(item.figure.startswith("<svg "), item.key)
            self.assertIn('viewBox="', item.figure)
            for bad in ("<script", "href", "url(", "javascript:", "foreignObject", " on"):
                self.assertNotIn(bad, item.figure, item.key)
            self.assertTrue(figures.is_safe(item.figure), item.key)

    def test_unsafe_figure_refused(self):
        item = self.geo.item_ids[:1]
        for svg in UNSAFE:
            self.assertFalse(figures.is_safe(svg), svg)
            with self.assertRaises(ValidationError), mute_logger("odoo.sql_db"), self.env.cr.savepoint():
                item.figure = svg

    def test_other_decks_have_no_figure(self):
        self.Deck.action_load_grammar_fr()
        others = self.Deck.search([("name", "!=", DECK)]).item_ids
        self.assertTrue(others)
        self.assertFalse(others.filtered("figure"))

    # 6 --------------------------------------------------------------------
    def test_facts_match_the_figures(self):
        checked = 0
        for item in self.geo.item_ids.filtered("figure_spec"):
            facts = figures.facts(item.figure_spec)
            prompt = plain(item.prompt)
            wrong = item.choice_ids.filtered(lambda c: not c.correct).mapped("label")
            if item.answer_mode == "keypad":
                if "rayon" in prompt or "diamètre" in prompt:
                    continue  # checked in test_radius_diameter
                word = re.search(r"(côtés|sommets|faces|arêtes)", prompt).group(1)
                key = {"côtés": "sides", "sommets": "vertices", "faces": "faces", "arêtes": "edges"}[word]
                self.assertEqual(int(item.answer), facts[key], item.key)
            elif prompt.startswith("Cette ligne est"):
                self.assertFalse(facts["closed"], item.key)
                self.assertIn(facts["line"], item.answer, item.key)
            elif "est-elle un polygone" in prompt:
                self.assertEqual(item.answer.startswith("Oui"), facts["polygon"], item.key)
                for label in wrong:
                    self.assertNotEqual(label.startswith("Oui"), facts["polygon"], item.key)
            elif prompt.startswith("Ce polygone est"):
                self.assertEqual(item.answer, "convexe" if facts["convex"] else "non convexe", item.key)
            elif prompt.startswith("Quel est ce polygone"):
                self.assertEqual(item.answer, "un %s" % facts["name"], item.key)
            elif prompt.startswith("Quel est ce triangle"):
                self.assertIn(item.answer, facts["triangle"], item.key)
                for label in wrong:
                    self.assertNotIn(label, facts["triangle"], item.key)
            elif prompt.startswith("Ce triangle est"):
                self.assertTrue(set(item.answer.split(" et ")) <= facts["triangle"], item.key)
                for label in wrong:
                    self.assertFalse(set(label.split(" et ")) <= facts["triangle"], item.key)
            elif "ce quadrilatère" in prompt:
                self.assertEqual(item.answer.split(" (")[0], figures.most_specific(facts["quad"]), item.key)
            elif "partie en orange" in prompt:
                self.assertEqual(item.answer, CIRCLE_PARTS[facts["mark"]], item.key)
            elif prompt.startswith("Cet angle est"):
                self.assertEqual(item.answer, facts["angle"], item.key)
            elif prompt.startswith("Ces deux droites sont"):
                self.assertEqual(item.answer, facts["lines"], item.key)
            elif "perpendiculaires ?" in prompt:
                self.assertEqual(item.answer.startswith("Oui"), facts["lines"] == "perpendiculaires", item.key)
            elif prompt.startswith("Quel est ce solide"):
                self.assertEqual(item.answer, solid_word(facts["solid"]), item.key)
                for label in wrong:
                    self.assertNotEqual(label, solid_word(facts["solid"]), item.key)
                    if facts["solid"] == "cube":
                        self.assertNotEqual(label, "un prisme", item.key)
            elif prompt.startswith("Un prisme a"):
                self.assertTrue(facts["solid"].startswith("prisme"), item.key)
            else:
                self.fail("no check for the figure card %s (%s)" % (item.key, prompt))
            checked += 1
        self.assertGreaterEqual(checked, 40)

    def test_solid_models(self):
        for kind, expected in SOLID_TABLE.items():
            faces, edges, vertices = figures.solid_counts(kind)
            self.assertEqual((faces, edges, vertices), expected, kind)
            self.assertEqual(faces + vertices - edges, 2, kind)  # Euler
        for item in self.geo.item_ids.filtered(lambda i: i.answer_mode == "keypad" and not i.figure_spec):
            m = re.fullmatch(r"Un cube a ___ (faces|arêtes|sommets)\.", plain(item.prompt))
            if m:
                self.assertEqual(int(item.answer), SOLID_TABLE["cube"][["faces", "arêtes", "sommets"].index(m.group(1))])

    def test_radius_diameter(self):
        n = 0
        for item in self.unit("Le cercle").item_ids.filtered(lambda i: i.answer_mode == "keypad"):
            m = re.fullmatch(r"Le (rayon|diamètre) mesure (\d+) (\w+)\. Le (rayon|diamètre) mesure ___ (\w+)\.",
                             plain(item.prompt))
            self.assertTrue(m, item.prompt)
            given, value, unit_a, asked, unit_b = m.groups()
            self.assertNotEqual(given, asked)
            self.assertEqual(unit_a, unit_b)
            value = int(value)
            self.assertEqual(int(item.answer), value * 2 if given == "rayon" else value // 2, item.prompt)
            self.assertTrue(given == "rayon" or value % 2 == 0, item.prompt)
            if item.figure_spec:
                self.assertIn("label=%s_%s" % (value, unit_a), item.figure_spec)
                self.assertIn("mark=%s" % ("radius" if given == "rayon" else "diameter"), item.figure_spec)
            n += 1
        self.assertGreaterEqual(n, 4)

    # 7 --------------------------------------------------------------------
    def test_sizes_and_orientations_vary(self):
        specs = self.geo.item_ids.mapped("figure_spec")
        self.assertIn("quad kind=square rot=45", " ".join(s for s in specs if s))
        by_kind = {}
        for spec in filter(None, specs):
            kind, params = figures.parse(spec)
            by_kind.setdefault(kind, []).append((params.get("rot", "0"), params.get("s", "1")))
        for kind in ("tri", "quad", "circle", "angle", "solid"):
            self.assertGreater(len({s for _r, s in by_kind[kind]}), 1, "%s in several sizes" % kind)
        for kind in ("tri", "quad", "angle", "lines"):
            self.assertGreater(len({r for r, _s in by_kind[kind]}), 2, "%s in several orientations" % kind)

    # 9 --------------------------------------------------------------------
    def test_synthetic(self):
        items = self.geo.item_ids
        texts = " ".join(items.mapped(lambda i: "%s %s %s %s" % (
            i.prompt, i.hint, i.unit_id.intro, " ".join(i.choice_ids.mapped("label")))))
        for name in ("Felix", "Félix", "Josée", "Joss", "Denis"):
            self.assertNotIn(name, texts)


@tagged("post_install", "-at_install")
class TestGeometryApi(PracticeHttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Unit = cls.env["homeschool.practice.unit"]
        cls.shapes = cls.env["homeschool.practice.deck"].create({"name": "Shapes", "intro_size": 2})
        unit = Unit.create({"deck_id": cls.shapes.id, "name": "Shapes", "sequence": 1})
        cls.shapes._generate_choice_cards(unit, [
            ("sh-1", "Quel est ce triangle ?", [("isocèle", True), ("scalène", False)], "x",
             "tri kind=isosceles rot=20"),
            ("sh-2", "Un triangle a ___ côtés.", "3", "x"),
        ])
        unit.action_unlock(cls.student)

    def test_figure_is_data_only(self):
        self.authenticate("hs_learner", "hs_learner")
        res = self.call("/session/start", deck_id=self.shapes.id, input_type="touch")
        seen, item, n = {}, res["item"], 0
        while item and n < 10:
            seen[plain(item["prompt"])] = item["figure"]
            out = self.call("/session/answer", session_id=res["session_id"], item_id=item["item_id"],
                            given=item["answer"], first_touch_ms=900, submit_ms=1400, client_uuid="g%s" % n)
            item, n = out.get("next"), n + 1
        figure = seen["Quel est ce triangle ?"]
        self.assertTrue(figure.startswith("data:image/svg+xml;base64,"), figure[:40])
        svg = base64.b64decode(figure.split(",", 1)[1]).decode()
        self.assertEqual(svg, figures.render("tri kind=isosceles rot=20"))
        self.assertTrue(figures.is_safe(svg))
        self.assertEqual(seen["Un triangle a ___ côtés."], "")

    def test_screen_shows_an_image(self):
        js = self.url_open("/homeschool_practice/static/src/js/practice.js").text
        self.assertIn('<img class="hp-figure"', js)
        self.assertIn("data:image\\/svg\\+xml;base64,", js)  # only a data URI of an SVG is shown
        css = self.url_open("/homeschool_practice/static/src/css/practice.css").text
        self.assertIn(".hp-figure", css)
