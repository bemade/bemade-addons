"""Task 1540 — the clinic sign-in kiosk on the Fit Crew brand tokens, with NO
off-domain request. Synthetic fixtures only.

Acceptance criteria (AC4):

* Every kiosk screen (pairing, form, result) loads ONE stylesheet bundle,
  ``bemade_sports_clinic.assets_kiosk``, CSS only (no JS bundle, no
  ``<script src>``), no inline ``<style>`` and no ``style=`` attribute; the
  three inline scripts stay (bfcache guard, idle reset, pairing poll).
* No URL on the page and no ``url()`` / ``@import`` in the stylesheet points
  to another host; the stylesheet declares the self-hosted Teko / DM Sans
  faces and both font files are served locally.
* The brand tokens reach the kiosk root (``.o_sc_kiosk_body``) and the
  shell no longer asks Google Fonts either.
"""
import re

from lxml import html as lxml_html

from odoo.tests import tagged

from .test_clinic_kiosk_device_1433 import TestClinicKioskDevice

OFF_DOMAIN_ATTR = re.compile(r'(?:href|src|action|content|srcset)\s*=\s*"[^"]*?(?:https?:)?//', re.I)
OFF_DOMAIN_CSS = re.compile(r'(?:url\(\s*["\']?(?:https?:)?//|@import)', re.I)
FONTS = (
    '/bemade_sports_clinic/static/src/fonts/Teko-Variable-latin.woff2',
    '/bemade_sports_clinic/static/src/fonts/DMSans-Variable-latin.woff2',
)


@tagged('-at_install', 'post_install')
class TestClinicKioskBrand1540(TestClinicKioskDevice):
    """Reuses the #1433 fixtures; Odoo collects a class's OWN test methods
    only, so the parent's tests do not run twice."""

    def _pages(self):
        device = self._bind()
        device._unbind()
        pages = [self.url_open('/clinic/kiosk')]
        self.Device._pair(device._current_pairing_code(), self.clinic)
        pages.append(self.url_open('/clinic/kiosk'))
        pages.append(self.url_open('/clinic/kiosk?done=ok'))
        return pages

    def test_brand_1540_css_only_bundle_no_inline_style(self):
        for resp in self._pages():
            self.assertEqual(resp.status_code, 200)
            text = resp.text
            tree = lxml_html.fromstring(text)
            self.assertNotIn('<style', text)
            self.assertFalse(tree.xpath('//*[@style]'))
            self.assertFalse(tree.xpath('//script[@src]'), 'no JS bundle on the kiosk')
            sheets = tree.xpath('//link[@rel="stylesheet"]/@href')
            self.assertTrue(sheets)
            self.assertTrue(all('bemade_sports_clinic.assets_kiosk' in href for href in sheets), sheets)
            self.assertTrue(tree.xpath('//body[contains(@class, "o_sc_kiosk_body")]'))
            self.assertTrue(tree.xpath('//img[@src="/bemade_sports_clinic/static/src/img/sc_logo_chrome.png"]'))
            self.assertIn('pageshow', text)

    def test_brand_1540_no_off_domain_request(self):
        pages = self._pages()
        for resp in pages:
            self.assertFalse(OFF_DOMAIN_ATTR.search(resp.text), OFF_DOMAIN_ATTR.search(resp.text))
            self.assertNotIn('fonts.googleapis', resp.text)
            self.assertNotIn('fonts.gstatic', resp.text)
        href = lxml_html.fromstring(pages[0].text).xpath('//link[@rel="stylesheet"]/@href')[0]
        css = self.url_open(href)
        self.assertEqual(css.status_code, 200)
        self.assertFalse(OFF_DOMAIN_CSS.search(css.text), OFF_DOMAIN_CSS.search(css.text))
        for font in FONTS:
            self.assertIn(font, css.text)
            self.assertEqual(self.url_open(font).status_code, 200, font)
        # The brand tokens reach the kiosk root.
        self.assertRegex(css.text, r'\.o_sc_kiosk_body\s*\{[^}]*--sc-forest')

    def test_brand_1540_shell_has_no_google_fonts(self):
        arch = self.env.ref('bemade_sports_clinic.sc_app_layout').arch_db
        self.assertNotIn('fonts.googleapis', arch)
        self.assertNotIn('fonts.gstatic', arch)

