"""Task 1793 (epic #1535, P4b) — the lint guard covers every clinic app
template FILE, not only the views whose key starts with ``sc_`` (the
database check of test_app_shell_pwa_1542 stays). Pure file checks.

Acceptance criteria covered here:

* UC-L1 No ``<script`` element in any app template file: ``views/sc_*.xml``
  (sc_no_access.xml included), the OWL templates ``static/src/js/*.xml`` and
  the templates the app renders inside its pages
  (``team_digest_portal_templates.xml``, ``portal_widgets_templates.xml``).
* UC-L2 No inline ``style=`` and no ``t-att-style`` / ``t-attf-style`` in
  those files, except the allow-listed dynamic values that must stay inline
  (``ALLOWED_DYNAMIC_STYLES``: none today). The digest renderer's two inline
  styles moved to classes (dashboard_digest.scss, loaded in both bundles).
* UC-L3 The allow-list is not stale: every allowed entry still exists.
"""
import glob
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import BaseCase, tagged

# The templates the app (/my, the kit shell) renders. The kiosk
# (clinic_kiosk_templates.xml) and the backend views are not the app.
APP_TEMPLATE_GLOBS = (
    'views/sc_*.xml',
    'static/src/js/*.xml',
    'views/team_digest_portal_templates.xml',
    'views/portal_widgets_templates.xml',
)

# (file relative to the addon, the exact attribute text) of the dynamic
# values that must stay inline, e.g. a computed width. Keep it short and
# give each entry its reason.
ALLOWED_DYNAMIC_STYLES = ()

STYLE_RE = re.compile(r'\s(?:t-att-|t-attf-)?style\s*=\s*("[^"]*"|\'[^\']*\')')
SCRIPT_RE = re.compile(r'<script\b', re.I)
COMMENT_RE = re.compile(r'<!--.*?-->', re.S)


def _app_template_files():
    root = get_module_path('bemade_sports_clinic')
    files = set()
    for pattern in APP_TEMPLATE_GLOBS:
        files.update(glob.glob(os.path.join(root, pattern)))
    return root, sorted(files)


@tagged('post_install', '-at_install')
class TestAppAuditLint1793(BaseCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.root, cls.files = _app_template_files()
        cls.sources = {}
        for path in cls.files:
            with open(path, encoding='utf-8') as handle:
                # Comments may talk ABOUT <script> / style= (they do).
                cls.sources[os.path.relpath(path, cls.root)] = COMMENT_RE.sub('', handle.read())

    def test_covers_every_app_template_file(self):
        names = set(self.sources)
        for expected in ('views/sc_no_access.xml', 'views/sc_app_layout.xml', 'views/sc_components.xml',
                         'views/sc_app_players.xml', 'static/src/js/sc_clinic_worklist.xml',
                         'views/team_digest_portal_templates.xml'):
            self.assertIn(expected, names)
        self.assertGreaterEqual(len([n for n in names if n.startswith('views/sc_')]), 15)

    # -- UC-L1 -----------------------------------------------------------
    def test_no_inline_script(self):
        offenders = [name for name, text in self.sources.items() if SCRIPT_RE.search(text)]
        self.assertFalse(offenders, 'inline <script> in: %s' % offenders)

    # -- UC-L2 -----------------------------------------------------------
    def test_no_inline_style(self):
        allowed = set(ALLOWED_DYNAMIC_STYLES)
        offenders = []
        for name, text in self.sources.items():
            for match in STYLE_RE.finditer(text):
                if (name, match.group(0).strip()) not in allowed:
                    offenders.append('%s: %s' % (name, match.group(0).strip()[:80]))
        self.assertFalse(offenders, 'inline style in app templates:\n%s' % '\n'.join(offenders))

    # -- UC-L3 -----------------------------------------------------------
    def test_allow_list_not_stale(self):
        for name, attribute in ALLOWED_DYNAMIC_STYLES:
            self.assertIn(attribute, self.sources.get(name, ''), name)
