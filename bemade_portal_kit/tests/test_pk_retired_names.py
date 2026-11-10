# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5198 (P3a): the kit scripts' markup contract takes ``pk`` names.

The names the kit scripts read or write moved from ``sc`` to ``pk``:

* 32 ``data-sc-*`` attributes -> ``data-pk-*`` (``dataset.scX`` ->
  ``dataset.pkX``);
* 7 ``sc:*`` events -> ``pk:*``;
* the storage keys ``sc_draft:``, ``sc_pending_toast:v1``,
  ``sc_nav_{stack,post,up,bf_reload}:v1`` and ``sc_filters_open:``.

This guard scans the kit and its consumers that are on the addons path
(views, static JS / XML / SCSS, controllers, models, tests and tours) and
fails on any retired name, with its file:line. A retired name in an addon
would be a dead hook: the kit no longer reads it. A consumer absent from
the path is skipped, so on a kit-only install only the kit is scanned.

The one exception is the documented draft fallback of the kit
(``pk_draft_store.js`` still reads ``sc_draft:`` once, and its hoot test
checks that).
"""
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

KIT = 'bemade_portal_kit'
SCANNED_ADDONS = (KIT, 'bemade_sports_clinic', 'bemade_sports_clinic_bookings')
EXTENSIONS = ('.py', '.js', '.xml', '.scss', '.css', '.po')
SKIP_DIRS = {'__pycache__', 'node_modules', 'lib', 'description'}

ATTRIBUTES = (
    'app-shell', 'autosubmit', 'autosubmit-fallback', 'back', 'confirm',
    'confirm-ok', 'confirm-cancel', 'db', 'uid', 'display-href',
    'draft-prefix', 'edit-card', 'edit-done', 'filter-reset',
    'fragment-item', 'list-add-cancel', 'list-add-toggle', 'live-count-url',
    'live-eager', 'live-hide-zero', 'live-poll', 'live-tone-on',
    'live-tone-off', 'menu-popup', 'menu-toggle', 'section', 'submitted',
    'submitting', 'switch-off', 'switch-submit', 'user-menu-popup',
    'user-menu-toggle',
)
EVENTS = (
    'fragments', 'form-reset', 'create-success', 'lazy-loaded',
    'live-count-refresh', 'fetch-error', 'nav-sync',
)
STORAGE_KEYS = (
    'sc_draft:', 'sc_pending_toast:v1', 'sc_nav_stack:v1', 'sc_nav_post:v1',
    'sc_nav_up:v1', 'sc_nav_bf_reload:v1', 'sc_filters_open:',
)

# The draft fallback: (path relative to the addon, retired names allowed).
ALLOWED = {
    (KIT, '__manifest__.py'): {'sc_draft:'},  # documents the fallback
    (KIT, 'static/src/js/pk_draft_store.js'): {'sc_draft:'},
    (KIT, 'static/tests/pk_draft_store.test.js'): {'sc_draft:', 'data-sc-db', 'data-sc-uid'},
    (KIT, 'tests/test_pk_retired_names.py'): None,  # this file: every name
}


def _camel(name):
    head, *rest = name.split('-')
    return 'sc' + head.capitalize() + ''.join(part.capitalize() for part in rest)


def _alternation(names):
    # Longest first, so ``live-count-url`` is not read as ``live``.
    return '|'.join(re.escape(n) for n in sorted(names, key=len, reverse=True))


# ``data-sc-section`` but not ``data-sc-section-title`` (a longer name that
# the kit does not read stays a consumer name).
ATTRIBUTE_RE = re.compile(r'(?<![\w])data-sc-(%s)(?![\w-])' % _alternation(ATTRIBUTES))
DATASET_RE = re.compile(
    r'''dataset(?:\.|\[\s*["'])(%s)(?![\w])''' % _alternation([_camel(a) for a in ATTRIBUTES])
)
EVENT_RE = re.compile(r'(?<![\w:-])sc:(%s)(?![\w-])' % _alternation(EVENTS))
KEY_RE = re.compile(_alternation(STORAGE_KEYS))


def retired_names(line):
    """The retired names found on ``line`` (as they appear)."""
    found = []
    found += [m.group(0) for m in ATTRIBUTE_RE.finditer(line)]
    found += [m.group(0) for m in DATASET_RE.finditer(line)]
    found += [m.group(0) for m in EVENT_RE.finditer(line)]
    found += [m.group(0) for m in KEY_RE.finditer(line)]
    return found


def _allowed(addon, relpath, name):
    if (addon, relpath) not in ALLOWED:
        return False
    names = ALLOWED[(addon, relpath)]
    return names is None or name in names


def scan(addon, root):
    hits = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith('.'))
        for filename in sorted(filenames):
            if not filename.endswith(EXTENSIONS):
                continue
            path = os.path.join(dirpath, filename)
            relpath = os.path.relpath(path, root).replace(os.sep, '/')
            with open(path, encoding='utf-8', errors='replace') as f:
                for lineno, line in enumerate(f, 1):
                    for name in retired_names(line):
                        if not _allowed(addon, relpath, name):
                            hits.append(f'{addon}/{relpath}:{lineno}: {name}')
    return hits


@tagged('post_install', '-at_install')
class TestPkRetiredNames(TransactionCase):

    def test_matcher(self):
        self.assertEqual(retired_names('<div data-sc-section="notes">'), ['data-sc-section'])
        self.assertEqual(retired_names('<div data-sc-section-title="1">'), [])
        self.assertEqual(retired_names('<div data-sc-edit-card-body="1">'), [])
        self.assertEqual(retired_names('<div t-att-data-sc-live-count-url="u">'), ['data-sc-live-count-url'])
        self.assertEqual(retired_names('<div data-sc-theme="dark">'), [])
        self.assertEqual(retired_names('el.dataset.scSection'), ['dataset.scSection'])
        self.assertEqual(retired_names('el.dataset.scSectionTitle'), [])
        self.assertEqual(retired_names('ev.type === "sc:fragments"'), ['sc:fragments'])
        self.assertEqual(retired_names('"sc:fragments-done"'), [])
        self.assertEqual(retired_names('`sc:nav-sync`'), ['sc:nav-sync'])
        self.assertEqual(retired_names('get("sc_nav_bf_reload:v1")'), ['sc_nav_bf_reload:v1'])
        self.assertEqual(retired_names("'sc_filters_open': True"), [])
        self.assertEqual(retired_names('<div data-pk-section="notes"> pk:fragments pk_draft:'), [])

    def test_no_retired_name_left(self):
        hits = []
        for addon in SCANNED_ADDONS:
            root = get_module_path(addon, display_warning=False)
            if root:
                hits += scan(addon, root)
        self.assertFalse(hits, 'retired sc names (task 5198, use the pk names):\n' + '\n'.join(hits))
