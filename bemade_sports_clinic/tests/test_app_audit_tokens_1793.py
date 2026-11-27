"""Task 1793 (epic #1535, P4b) — the app's colour tokens meet WCAG AA, and
the brand colours stay as the brand guide has them. Pure file checks.

Acceptance criteria covered here:

* UC-C1 The text tokens that failed AA in the Lighthouse / axe audit meet
  4.5:1 against the grounds they are drawn on, the ratio COMPUTED from the
  values in ``static/src/scss/sc_tokens.scss`` (so a later edit cannot drop
  them below AA silently):
  - dark ``--pk-fg-3`` on ``--pk-surface`` and on ``--pk-bg``;
  - light ``--pk-ok`` and ``--pk-warn`` on ``--pk-surface`` and ``--pk-bg``,
    and ``--pk-tone-fg`` (white) on them (the filled status chips);
  - ``--pk-secondary-fg`` on ``--pk-secondary`` (the filled tab / chip), set
    by each theme (dark: Minuit, light: white on Mauve).
* UC-C2 The six brand colours (Forêt, Vert néon, Mauve, Minuit, Charbon,
  Gris) are unchanged.
"""
import re

from odoo.tests import BaseCase, tagged
from odoo.tools import file_open

TOKENS = 'bemade_sports_clinic/static/src/scss/sc_tokens.scss'
AA = 4.5


def _mixin(source, name):
    """{--token: value} of one ``@mixin name { ... }`` of the SCSS file."""
    match = re.search(r'@mixin %s\s*\{(.*?)\n\}' % re.escape(name), source, re.S)
    assert match, name
    return dict(re.findall(r'(--[\w-]+)\s*:\s*([^;]+);', match.group(1)))


def _luminance(hex_colour):
    value = hex_colour.strip().lstrip('#')
    if len(value) == 3:
        value = ''.join(c * 2 for c in value)
    channels = [int(value[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    channels = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast_ratio(fg, bg):
    """The WCAG 2.x contrast ratio of two #rrggbb colours."""
    high, low = sorted((_luminance(fg), _luminance(bg)), reverse=True)
    return (high + 0.05) / (low + 0.05)


@tagged('post_install', '-at_install')
class TestAppAuditTokens1793(BaseCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with file_open(TOKENS) as source:
            text = source.read()
        cls.brand = _mixin(text, 'sc-brand-tokens')
        cls.dark = _mixin(text, 'sc-theme-dark')
        cls.light = _mixin(text, 'sc-theme-light')

    def assertAA(self, theme, fg, bg, tokens):
        ratio = contrast_ratio(tokens[fg], tokens[bg])
        self.assertGreaterEqual(
            round(ratio, 2), AA, '%s %s %s on %s %s = %.2f:1' % (theme, fg, tokens[fg], bg, tokens[bg], ratio))

    def test_ratio_helper(self):
        self.assertAlmostEqual(contrast_ratio('#000000', '#ffffff'), 21.0, places=2)
        self.assertAlmostEqual(contrast_ratio('#767676', '#ffffff'), 4.54, places=2)

    # -- UC-C1 -----------------------------------------------------------
    def test_dark_fg3_meets_aa(self):
        for ground in ('--pk-surface', '--pk-bg'):
            self.assertAA('dark', '--pk-fg-3', ground, self.dark)

    def test_light_status_tokens_meet_aa(self):
        for token in ('--pk-ok', '--pk-warn'):
            for ground in ('--pk-surface', '--pk-bg'):
                self.assertAA('light', token, ground, self.light)
            # The filled chip: white text on the status colour.
            ratio = contrast_ratio(self.light['--pk-tone-fg'], self.light[token])
            self.assertGreaterEqual(round(ratio, 2), AA, '%s chip %.2f:1' % (token, ratio))

    def test_secondary_fill_meets_aa(self):
        # Each theme sets its own: the light rule must not inherit the
        # dark theme's (both rules match the shell root).
        for theme, tokens in (('dark', self.dark), ('light', self.light)):
            self.assertIn('--pk-secondary-fg', tokens, theme)
            self.assertAA(theme, '--pk-secondary-fg', '--pk-secondary', tokens)

    def test_other_text_tokens_meet_aa(self):
        """The rest of the text tokens stay AA on their grounds (they did)."""
        for theme, tokens in (('dark', self.dark), ('light', self.light)):
            for fg in ('--pk-fg', '--pk-fg-2', '--pk-bad', '--pk-overdue'):
                for ground in ('--pk-surface', '--pk-bg'):
                    self.assertAA(theme, fg, ground, tokens)
        for fg in ('--pk-ok', '--pk-warn'):
            for ground in ('--pk-surface', '--pk-bg'):
                self.assertAA('dark', fg, ground, self.dark)
        self.assertAA('light', '--pk-fg-3', '--pk-surface', self.light)
        self.assertAA('light', '--pk-fg-3', '--pk-bg', self.light)

    # -- UC-C2 -----------------------------------------------------------
    def test_brand_colours_unchanged(self):
        self.assertEqual({key: self.brand[key] for key in self.brand if key.startswith('--sc-')}, {
            '--sc-forest': '#243925',
            '--sc-neon': '#a4c754',
            '--sc-mauve': '#783e88',
            '--sc-midnight': '#120e12',
            '--sc-charcoal': '#302e33',
            '--sc-grey': '#e5e5e5',
        })
