# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5370 (P4b): the form guard's request header.

A guarded form in fetch mode (``@bemade_portal_kit/js/pk_form_guard``,
``data-pk-guard-mode="fetch"``) posts to its own action with
``X-Pk-Guard: 1`` and reads the page it lands on for a refusal. A page that
pops one-time session state (a notification, a proposal) peeks instead when
``PortalKitApp._pk_guard_probe()`` is True: the real navigation that
follows a success still shows it.
"""
PK_GUARD_HEADER = 'X-Pk-Guard'
