# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""19.0.1.6.0: « a quest every day » now means « until mastered », and the quests rotate.

* The flag stays on the times-tables decks (found by their item keys, « 7x8 ») and comes off
  « Grammaire » (found by name, in any installed language): grammar joins the rotation.
* The « perfect » quest template (``noupdate``) may now ask for 2 sessions: its default name
  gets a {target}. A name a family changed is left alone.
* Quests already drawn (today's included) are left as they are. Idempotent.
"""
from odoo import SUPERUSER_ID, api

OLD_PERFECT = "A session without a miss"
NEW_PERFECT = {"en": "{target} perfect session{s}", "fr": "{target} séance{s} parfaite{s}"}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["homeschool.practice.deck"]._flag_daily_decks()
    perfect = env.ref("homeschool_practice.quest_perfect", raise_if_not_found=False)
    if perfect and perfect.with_context(lang="en_US").name == OLD_PERFECT:
        perfect.with_context(lang="en_US").name = NEW_PERFECT["en"]
        # update_field_translations: a plain write in French would also overwrite en_US when
        # English is not an active language
        perfect.update_field_translations("name", {
            code: NEW_PERFECT["fr"] for code, _name in env["res.lang"].get_installed() if code.startswith("fr")})
