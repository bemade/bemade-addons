# -*- coding: utf-8 -*-
"""UC-04 — Attempts and silent timing.

Acceptance criteria
-------------------
1. ``homeschool.practice.attempt``: ``session_id`` (required, cascade), ``student_id``
   and ``company_id`` from the session, ``item_id``, ``given`` (the answer), ``correct``
   (computed by the server, never trusted from the client), ``hint_used``,
   ``first_touch_ms`` and ``submit_ms`` (integers ≥ 0, measured on the device from the
   moment the item is displayed), ``client_ts`` (when it happened on the device) and
   ``received_at`` (when the server got it).
2. Attempts sent late (offline queue) keep their ``client_ts``; a replayed attempt
   (same ``client_uuid``) is stored once.
3. Latencies above a sanity bound (default 120 s: he walked away) are kept but flagged
   ``outlier`` and ignored by mastery (UC-05).
4. The timing fields are restricted to the Homeschool manager group (field ``groups``);
   reading them as a portal user raises AccessError (see also UC-11).
"""
from odoo.addons.homeschool.tests.common import HomeschoolCase


class TestAttemptsTiming(HomeschoolCase):
    pass
