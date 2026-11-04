"""Task 1728 — the morning summary stays readable in dark mode (email side).
Synthetic fixtures only.

Mail clients that auto-darken either keep our inline greys on a dark
background or invert them, so a muted line must read on BOTH white and
black: one mid grey, #767676 (4.54:1 on white, 4.63:1 on black). No
``prefers-color-scheme`` in email.

Acceptance criteria covered here:

* UC-E1 Morning briefing (``mail_template_morning_digest``), rendered with
  a team line (announcement included) and upcoming events: every inline
  ``color`` has a contrast ≥ 4.5:1 against white AND black, and the muted
  meta lines use #767676.
* UC-E2 Its fallback body (``res.users._digest_fallback_body``): same.
* UC-E3 The sibling urgent summary (``mail_template_urgent_summary`` and
  ``sports.patient._urgent_notify_fallback_body``) shares the meta line:
  same rule.

The in-app digest (app shell, both themes) is covered by the 1728 tour
(test_digest_dark_mode_tours_1728.py).
"""
import re

from lxml import html as lxml_html

from odoo import fields
from odoo.tests import TransactionCase, tagged

MUTED = '#767676'
MIN_RATIO = 4.5


def _rgb(value):
    value = value.strip().lower()
    m = re.fullmatch(r'#([0-9a-f]{3}|[0-9a-f]{6})', value)
    if m:
        hexa = m.group(1)
        if len(hexa) == 3:
            hexa = ''.join(c * 2 for c in hexa)
        return tuple(int(hexa[i:i + 2], 16) for i in (0, 2, 4))
    m = re.fullmatch(r'rgba?\(([^)]+)\)', value)
    if m:
        return tuple(int(float(v)) for v in m.group(1).split(',')[:3])
    named = {'black': (0, 0, 0), 'white': (255, 255, 255)}
    if value in named:
        return named[value]
    raise AssertionError('unparsed colour %r' % value)


def _luminance(rgb):
    def lin(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast(fg, bg):
    a, b = _luminance(_rgb(fg)), _luminance(_rgb(bg))
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


def inline_colours(body):
    """(colour, text) for every element whose inline style sets ``color``."""
    tree = lxml_html.fromstring('<div>%s</div>' % body)
    out = []
    for el in tree.xpath('//*[@style]'):
        for decl in el.get('style').split(';'):
            prop, _sep, value = decl.partition(':')
            if prop.strip().lower() == 'color':
                out.append((value.replace('!important', '').strip(),
                            ' '.join(el.text_content().split())))
    return out


class DigestEmailContrastCase(TransactionCase):

    def assertReadableOnBoth(self, body, min_lines):
        colours = inline_colours(body)
        self.assertGreaterEqual(len(colours), min_lines, body)
        for colour, text in colours:
            for bg in ('#ffffff', '#000000'):
                ratio = contrast(colour, bg)
                self.assertGreaterEqual(
                    ratio, MIN_RATIO,
                    '%s on %s = %.2f:1 « %s »' % (colour, bg, ratio, text[:60]))
        return colours


@tagged('post_install', '-at_install')
class TestDigestEmailDarkMode1728(DigestEmailContrastCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Synthetic Recipient 1728', 'email': 'r1728@example.com'})
        cls.team_lines = [{
            'name': 'Synthetic Squad 1728',
            'announcement': 'Synthetic note for all staff.',
            'announcement_is_expired': False,
            'red': 2, 'red_delta_str': ' (+1)',
            'yellow': 1, 'yellow_delta_str': '',
            'delta_red': 1, 'delta_yellow': 0,
            'new_injuries': 1, 'changes': 3,
            'pending_verify': 1, 'pending_removal': 0,
            'url': 'https://example.com/my/team/1',
        }]
        cls.events = [{
            'name': 'Synthetic Game 1728',
            'date_start': fields.Datetime.now(),
            'date_label': 'Sat 12:00',
            'assigned': True, 'assigned_label': 'Synthetic Squad 1728',
        }]

    def _render_morning(self):
        template = self.env.ref('bemade_sports_clinic.mail_template_morning_digest')
        return template.with_context(
            digest_teams=self.team_lines, digest_events=self.events,
            digest_window_hours=24, digest_events_days=14,
        )._render_field('body_html', self.partner.ids)[self.partner.id]

    # -- UC-E1 -----------------------------------------------------------
    def test_morning_template_muted_lines_read_on_white_and_black(self):
        body = self._render_morning()
        # The window header, the events note and the « no medical data » line.
        colours = self.assertReadableOnBoth(body, min_lines=3)
        self.assertEqual({c.lower() for c, _t in colours}, {MUTED})

    # -- UC-E2 -----------------------------------------------------------
    def test_morning_fallback_muted_lines_read_on_white_and_black(self):
        body = self.env['res.users']._digest_fallback_body(
            self.team_lines, self.events, window_hours=24, events_days=14)
        colours = self.assertReadableOnBoth(body, min_lines=2)
        self.assertEqual({c.lower() for c, _t in colours}, {MUTED})

    # -- UC-E3 -----------------------------------------------------------
    def test_urgent_summary_muted_line_reads_on_white_and_black(self):
        teams = [{
            'name': 'Synthetic Squad 1728', 'status_changes': 1,
            'new_injuries': 1, 'events': [], 'url': 'https://example.com/my/team/1',
        }]
        template = self.env.ref('bemade_sports_clinic.mail_template_urgent_summary')
        body = template.with_context(urgent_teams=teams)._render_field(
            'body_html', self.partner.ids)[self.partner.id]
        self.assertReadableOnBoth(body, min_lines=1)
        fallback = self.env['sports.patient']._urgent_notify_fallback_body(teams)
        self.assertReadableOnBoth(fallback, min_lines=1)

    def test_contrast_helper(self):
        """The reference values the rule rests on."""
        self.assertLess(contrast('#888888', '#ffffff'), MIN_RATIO)  # the old grey
        self.assertGreaterEqual(contrast(MUTED, '#ffffff'), MIN_RATIO)
        self.assertGreaterEqual(contrast(MUTED, '#000000'), MIN_RATIO)
