# -*- coding: utf-8 -*-
"""UC-12 — Portal practice screen (touch first, progress always in sight).

Acceptance criteria
-------------------
1. ``homeschool.student``: ``practice_handedness`` (``right`` | ``left``, default
   ``right``) and ``practice_weekdays`` (UC-07 §7), set by a manager; the lesson screen
   puts the keypad / choices on the dominant-hand side.
2. ``/my/homeschool/practice`` (the home) shows, without scrolling on an iPad in
   landscape: the day's quests as cards to pick from, the level and XP bar, the day /
   week / month goals, the reward balances (« en banque », per type) and the latest
   badges. A link appears on the homeschool portal home card.
3. The lesson screen has **no text input** (no iPad keyboard): keypad items use an
   on-screen number pad (0–9, erase, « Valider »); choices items use large buttons. No
   clock, countdown or speed anywhere; no item-level « je le sais » label.
4. Celebration on every finished session, quest, goal, level and badge (praise for the
   work done, not for speed or for « knowing »).
5. Touch targets ≥ 64 px; zoom gestures disabled on the page; a web-app manifest so it
   can be added to the iPad home screen and open full screen. Target: Safari on
   iPadOS 17 and later.
6. Answers not yet sent (no network) are queued on the device and sent in order when
   the connection returns (each with its ``client_uuid``).
7. Rendering is checked by HttpCase tests; real touch behaviour is checked by hand on
   the iPad before release (noted in the review artifact).
"""
from odoo.addons.homeschool.tests.common import HomeschoolCase


class TestPortalScreen(HomeschoolCase):
    pass
