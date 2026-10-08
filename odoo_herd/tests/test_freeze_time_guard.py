# Acceptance criteria:
#   * With kubernetes.client loaded (as this module does), freezing time works
#     and the clock runs again once the freeze ends. Without the module's
#     freezegun guard, starting the freeze raises and the clock stays frozen
#     for the rest of the test run.

import time
from datetime import datetime

import kubernetes.client  # noqa: F401  loaded by this module in production too
from freezegun import freeze_time

from odoo import fields
from odoo.tests.common import TransactionCase


class TestFreezeTimeGuard(TransactionCase):
    def test_freeze_time_with_kubernetes_loaded(self):
        frozen = datetime(2026, 3, 2, 9, 0, 0)
        with freeze_time(frozen):
            self.assertEqual(fields.Datetime.now(), frozen)
        self.assertGreater(time.time(), frozen.timestamp() + 86400)
