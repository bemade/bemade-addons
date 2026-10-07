# Copyright 2026 Bemade Inc. <marc@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).


def _backfill_sale_usage_ranks(env):
    """Set every partner's sales usage counters from existing orders."""
