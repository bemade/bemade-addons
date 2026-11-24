# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5369 (kit P3c1): the kit's icon, ``bemade_portal_kit.pk_icon``.

* UC-I1 ``pk_icon`` renders an inline SVG (24 x 24, stroke ``currentColor``
  from the ``o_pk_icon`` class) selected by ``icon``; the markup of every kit
  glyph is byte-identical to what the first consumer rendered before the move
  (golden strings captured on bemade-addons 19.0 @ 5917030f).
* UC-I2 An unknown or empty name renders the fallback (three dots), through
  the extension point ``pk_icon_extra``, which a consumer inherits to add its
  own glyphs before the fallback.
* UC-I3 The glyphs are Feather Icons 4.29 (MIT) or drawn after them; the
  notice ships with the kit.
"""
from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

HEAD = '\n        <svg viewBox="0 0 24 24" class="o_pk_icon" aria-hidden="true" focusable="false">\n            '
TAIL = '\n        </svg>'
FALLBACK = '<circle cx="12" cy="12" r="1"></circle><circle cx="19" cy="12" r="1"></circle><circle cx="5" cy="12" r="1"></circle>'

# The 37 kit glyphs, as rendered before the move (sc_icon, 19.0 @ 5917030f).
GOLDEN = {
    'star': '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>',
    'activities': '<path d="M9 11l3 3L22 4"></path><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>',
    'calendar': '<rect x="3" y="4" width="18" height="18" rx="2"></rect><path d="M16 2v4M8 2v4M3 10h18"></path>',
    'note': '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><path d="M14 2v6h6M8 13h8M8 17h5"></path>',
    'clock': '<circle cx="12" cy="12" r="9"></circle><path d="M12 7v5l3 2"></path>',
    'summary': '<path d="M4 19V5M4 19h16M8 15v-4M12 15V8M16 15v-6"></path>',
    'account': '<circle cx="12" cy="8" r="4"></circle><path d="M4 21a8 8 0 0 1 16 0"></path>',
    'security': '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>',
    'settings': '<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6"></path>',
    'documents': '<path d="M3 7h18v13H3zM8 7V4h8v3"></path>',
    'backend': '<rect x="3" y="3" width="7" height="7" rx="1"></rect><rect x="14" y="3" width="7" height="7" rx="1"></rect><rect x="3" y="14" width="7" height="7" rx="1"></rect><rect x="14" y="14" width="7" height="7" rx="1"></rect>',
    'logout': '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"></path>',
    'back': '<path d="M15 18l-6-6 6-6"></path>',
    'chevron': '<path d="M9 18l6-6-6-6"></path>',
    'search': '<circle cx="11" cy="11" r="8"></circle><path d="M21 21l-4.35-4.35"></path>',
    'help': '<circle cx="12" cy="12" r="10"></circle><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path><path d="M12 17h.01"></path>',
    'moon': '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>',
    'sun': '<circle cx="12" cy="12" r="4"></circle><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"></path>',
    'up': '<path d="M18 15l-6-6-6 6"></path>',
    'down': '<path d="M6 9l6 6 6-6"></path>',
    'install': '<rect x="6" y="2" width="12" height="20" rx="2"></rect><path d="M12 7v7M9 11l3 3 3-3M10 18h4"></path>',
    'history': '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"></path><path d="M3 3v5h5M12 7v5l3 2"></path>',
    'megaphone': '<path d="M3 11v2a1 1 0 0 0 1 1h2l5 4V6L6 10H4a1 1 0 0 0-1 1zM15 9a3 3 0 0 1 0 6M18 6a7 7 0 0 1 0 12"></path>',
    'plus': '<path d="M12 5v14M5 12h14"></path>',
    'close': '<path d="M18 6L6 18M6 6l12 12"></path>',
    'share': '<path d="M12 3v12M8 7l4-4 4 4"></path><path d="M5 12v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7"></path>',
    'user': '<circle cx="12" cy="8" r="4"></circle><path d="M6 21v-1a6 6 0 0 1 12 0v1"></path>',
    'archive': '<path d="M21 8v13H3V8"></path><path d="M1 3h22v5H1z"></path><path d="M10 12h4"></path>',
    'edit': '<path d="M12 20h9"></path><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"></path>',
    'trash': '<path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6"></path>',
    'download': '<path d="M12 3v12M7 10l5 5 5-5M5 21h14"></path>',
    'upload': '<path d="M12 21V9M7 14l5-5 5 5M5 3h14"></path>',
    'phone': '<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.8.7 2.7a2 2 0 0 1-.5 2.1L8 9.8a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.7.7a2 2 0 0 1 1.9 2z"></path>',
    'mail': '<rect x="3" y="5" width="18" height="14" rx="2"></rect><path d="M3 7l9 6 9-6"></path>',
    'check': '<path d="M20 6L9 17l-5-5"></path>',
    'filter': '<path d="M22 3H2l8 9.5V19l4 2v-8.5z"></path>',
    'sort': '<path d="M7 4v16M3 16l4 4 4-4M17 20V4M13 8l4-4 4 4"></path>',
}


def render_icon(env, icon=None):
    values = {} if icon is None else {'icon': icon}
    return str(env['ir.qweb']._render('bemade_portal_kit.pk_icon', values))


@tagged('post_install', '-at_install')
class TestPkIcon(TransactionCase):

    def test_kit_glyphs_byte_identical(self):
        self.assertEqual(len(GOLDEN), 37)
        for name, inner in GOLDEN.items():
            with self.subTest(icon=name):
                self.assertEqual(render_icon(self.env, name), HEAD + inner + TAIL)

    def test_fallback(self):
        for icon in ('no-such-icon', '', None):
            with self.subTest(icon=icon):
                self.assertEqual(render_icon(self.env, icon), HEAD + FALLBACK + TAIL)

    def test_extension_point(self):
        """A consumer's glyph goes before the fallback of pk_icon_extra."""
        self.env['ir.ui.view'].create({
            'name': 'pk test: extra glyph',
            'type': 'qweb',
            'inherit_id': self.env.ref('bemade_portal_kit.pk_icon_extra').id,
            'arch': '<xpath expr="//t[@t-else]" position="before">'
                    '<t t-elif="icon == \'pk-test-glyph\'"><path d="M1 1h2"/></t></xpath>',
        })
        self.assertEqual(render_icon(self.env, 'pk-test-glyph'), HEAD + '<path d="M1 1h2"></path>' + TAIL)
        self.assertEqual(render_icon(self.env, 'no-such-icon'), HEAD + FALLBACK + TAIL)
        self.assertEqual(render_icon(self.env, 'plus'), HEAD + GOLDEN['plus'] + TAIL)

    def test_feather_notice(self):
        path = get_module_path('bemade_portal_kit') + '/static/src/icons/LICENSE-feather.txt'
        with open(path, encoding='utf-8') as f:
            text = f.read()
        self.assertIn('Feather', text)
        self.assertIn('Cole Bemis', text)
        self.assertIn('MIT', text)
