# -*- coding: utf-8 -*-
"""Shared fixtures for the homeschool use-case tests (filled in during TDD)."""
from odoo.tests import TransactionCase


class HomeschoolCase(TransactionCase):
    """A student, a school year, the five subjects, a handful of curriculum items."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # TODO (TDD): student "Felix", year 2026-2027, subjects FLE/MATH/ANG/ST/US,
        # items FLE-E-SYN-C-E.2.a.i, MATH-MES-G.1, US-C1-1820, K1-ENGAGE (internal).
