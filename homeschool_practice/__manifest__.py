# -*- coding: utf-8 -*-
# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
{
    "name": "Homeschool Practice",
    "version": "19.0.1.10.0",
    "category": "Education",
    "summary": "Short, frequent retrieval practice with game mechanics and family-defined rewards, "
    "touch-first (iPad).",
    "description": """
Homeschool Practice
===================

Short, frequent retrieval practice for home-schooled learners, with game
mechanics and family-defined rewards. Built for touch devices (iPad first).

Teach first, then practice
--------------------------
Practice items (multiplication facts, spelling, grammar cards…) are grouped in
decks (subject areas) and units (one times table, one grammar concept) linked to
curriculum items (``homeschool.item``). A unit stays locked until an adult has
taught it and unlocks it. Inside an unlocked unit, progression is automatic
(e.g. small multipliers first, larger ones as the first become secure), and
review sessions bring back items from every unlocked unit.

Server-side practice engine
---------------------------
The server chooses the next items (spaced repetition per learner and item),
records every attempt and tracks mastery per item (new → derived → automatic).
Mastery is a verdict for educators only: the learner is rewarded and
celebrated for doing the practice, never told which items he « knows ».
Front ends (the portal lesson screen now, other games later) only display items
and return answers, so learner history and progress are shared across them.

Starter decks a parent loads from the deck list: French grammar (homophones,
grammar, word classes, agreement, conjugation, syntax), math (« Les
fractions »: reading, comparing, fraction of a whole number, equivalent and
reduced fractions, ordering, fraction / decimal / percentage; « Les
conversions »: length, mass, capacity and time units; « La géométrie »: plane
figures and polygons, triangles, quadrilaterals, the circle, angles and lines,
solids) and English (« English
grammar »: irregular plurals, the possessive 's, past tense spelling and
irregular verbs, capitals and end marks, one idea per sentence; hints in
English), linked to the Québec PDA curriculum items they practise. « Additions
et soustractions » is loaded on its own (« Load additions and subtractions »):
generated keypad cards, the addition and subtraction facts up to 20, the
complements to 10 and to 100, then mental calculation with 2-digit numbers
(± 1 digit, ± whole tens, ± 2 digits), half of them crossing a ten.

A card can show a drawn figure (the geometry set): the deck's data gives a short
figure spec (« tri kind=isosceles rot=20 ») and the module draws it as an SVG
image, with the usual marks computed from the drawn geometry (tick marks on equal
sides, right-angle squares, parallel arrows, dashed hidden edges). The lesson
screen shows it as an image, never as markup, and shrinks it with the text so a
card never scrolls.

Each item has an answer mode: a **keypad** (the learner produces the answer —
e.g. multiplication facts) or **choices** (the learner picks — e.g. infinitive
or past participle).

Response time is measured silently (first touch and submit latency, tagged by
device and input type) and used only to assess automaticity against the
learner's own history on the same input type. It is never shown to the learner,
and the portal API never returns it.

Game mechanics
--------------
* XP and levels for effort and progress. XP is never earned for speed.
* Daily quests (by default 3 a day, together 3 to 5 distinct sessions, varied: a
  session that counts for several quests counts once); the learner chooses the order. A deck may get a quest every day until the learner has
  mastered it (« Une quête chaque jour jusqu'à la maîtrise »: the times tables);
  the other slots rotate among the unlocked decks, least recently quested first,
  never a deck twice a day. About one day in three, « surprise lessons » open a
  unit the app picks among those not practised for a while. Mastery stays a
  backend notion: the learner never sees it. A daily cap rewards spaced practice
  over cramming. Practice days are configured per learner.
* The size of the day is set per learner: how many quests, the range of
  sessions the day asks for, optional subject quests (« 3 séances de math »:
  any deck of the subject counts) and an optional practice-time quest
  (« Pratique 15 minutes aujourd'hui », on some days only, more often after light
  days, never three days in a row). Its « Start » opens a session in a unit
  picked at random at every click: the times tables about a third of the time,
  the other units weighted toward the least practised and longest unseen.
  Practice time counts each answer's
  gap since the previous one, capped at a minute, so an idle screen does not
  count; the learner sees the day's minutes on that quest card only, never
  inside a session. A bigger day makes the quests bigger, not more numerous,
  and it can arrive gradually: a ramp grows the sessions and the practice
  time week by week from the defaults to the learner's settings.
* Badges for accomplishments (XP reached, XP in a day, perfect sessions, unit
  proficiency levels…), never for speed or time of day.
* Daily, weekly and monthly goals built from completed quests (the day goal
  may be « all of today's quests »). No streaks.

Family-defined rewards
----------------------
Each family defines reward types per learner (gaming minutes, purchase
credit…) and what each goal pays. Rewards come from goals, not from XP. Earned
rewards go to a ledger, never expire, and are spent through parent-recorded
redemptions. Reward rates can change over time without rewriting history.
The learner always sees what he has in the bank.

Learner preferences
-------------------
Handedness (right / left) per learner: the touch layout puts the keypad and the
choices on the side of the learner's dominant hand.

In the portal app
-----------------
With the homeschool portal on the Bemade portal kit (``homeschool_portal``
19.0.3.0.0, the kit's switch on), practice is part of the app: a « Practice »
nav entry and the day's quests on « Today » (each with « Start »). For the
learner the game stays full screen (its own page, no app chrome) with a ✕ back
to « Today »; the installed app is the kit's (this addon no longer serves a
manifest of its own). For a tutor, « Practice » is a read-only page per learner:
the units unlocked, the proficiency of each and when it was last practised —
never shown to the learner. Every practice entry belongs to the homeschool app of
the kit (19.0.1.15.0 or later).

Multi-learner
-------------
Every record belongs to a learner (``homeschool.student``) and to the
learner's family (company). Learners see only their own data in the portal;
timing and mastery data are visible to educators (managers, and resource users
attached to the learner) only.
""",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": ["homeschool", "homeschool_portal", "bemade_portal_kit_dashboard"],
    "data": [
        "security/ir.model.access.csv",
        "security/practice_rules.xml",
        "data/practice_data.xml",
        "views/practice_views.xml",
        "views/portal_templates.xml",
        "views/practice_app.xml",
    ],
    "installable": True,
    "application": False,
}
