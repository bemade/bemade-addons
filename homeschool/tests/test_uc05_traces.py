# -*- coding: utf-8 -*-
"""UC-05 — Traces: dated artifacts for the portfolio, with a diffusion level.

Acceptance criteria
-------------------
1. ``homeschool.trace`` has ``code`` (``TR-YYYY-MM-DD-a``, generated: next letter for
   the date, unique), ``date``, ``name``, ``subject_ids``, ``item_ids``, attachments,
   ``diffusion`` (internal | institutional), ``note``, ``student_comment`` (the child's
   own words — portfolio content, never journal), ``block_id``, ``project_id``,
   ``submitted_by`` (parent | student).
2. An **institutional** trace cannot reference an internal-only item (kind =
   internal) — ValidationError, mirroring ``report.py check``.
3. Importing ``tracking/traces.csv`` preserves ``trace_id`` as code and external id,
   splits ``matieres`` and ``pda_ids`` on ``;``, attaches ``artifact_path`` when the
   file exists in the repository path given to the importer.
4. A trace created from a block inherits the block's date, subject and items as
   defaults.
5. Traces are ``mail.thread``: attachments and comments are tracked.
"""
from .common import HomeschoolCase


class TestTraces(HomeschoolCase):
    def test_code_generation(self):
        self.skipTest("pending — TDD")

    def test_institutional_refuses_internal_items(self):
        self.skipTest("pending — TDD")

    def test_traces_csv_import(self):
        self.skipTest("pending — TDD")

    def test_defaults_from_block(self):
        self.skipTest("pending — TDD")
