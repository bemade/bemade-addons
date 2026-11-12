# -*- coding: utf-8 -*-
# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
{
    "name": "Homeschool Practice",
    "version": "19.0.1.0.0",
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
* Daily quests drawn from what needs practice that day; the learner chooses
  the order. A daily cap rewards spaced practice over cramming. Practice days
  are configured per learner.
* Badges for accomplishments (XP reached, XP in a day, perfect sessions, unit
  proficiency levels…), never for speed or time of day.
* Daily, weekly and monthly goals built from completed quests. No streaks.

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
    "depends": ["homeschool", "homeschool_portal"],
    "data": [
        "security/ir.model.access.csv",
        "security/practice_rules.xml",
        "data/practice_data.xml",
        "views/practice_views.xml",
        "views/portal_templates.xml",
    ],
    "installable": True,
    "application": False,
}
