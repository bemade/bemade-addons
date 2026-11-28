"""Task 1793 / 1795, review round 2 (2026-11-27) — the staff bookings list
pages with the clinic's app pager (French « Précédent » / « Suivant »), like
the clinic's own lists. Synthetic fixtures only.

Acceptance criteria covered here:

* UC-P4 A paged staff « Réservations » list rendered for a fr_CA therapist
  names its pager links « Précédent » / « Suivant ».
* UC-P5 No bookings app template calls ``portal.pager``.
"""
import glob
import os
from unittest.mock import patch

from lxml import html as lxml_html

from odoo import Command
from odoo.modules.module import get_module_path
from odoo.tests import tagged

from odoo.addons.portal.controllers.portal import CustomerPortal

from .common import BookingsShellCommon


@tagged('post_install', '-at_install')
class TestBookingsPager1795(BookingsShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['res.lang']._activate_lang('fr_CA')
        env['ir.module.module']._load_module_terms(
            ['bemade_portal_kit', 'bemade_sports_clinic', 'bemade_sports_clinic_bookings'],
            ['fr_CA'], overwrite=True)
        if env['ir.module.module']._get('website').state == 'installed':
            fr_lang = env['res.lang']._lang_get('fr_CA')
            for website in env['website'].sudo().search([]):
                website.language_ids = [Command.link(fr_lang.id)]
        cls.tp.write({'lang': 'fr_CA'})

    def test_staff_bookings_pager_in_french(self):
        self._switch(True)
        self.authenticate('bk.tp@example.com', 'bk-tp-pass')
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        with patch.object(CustomerPortal, '_items_per_page', 1):
            resp = self.url_open('/my/bookings?filterby=all')
        self.assertEqual(resp.status_code, 200)
        tree = lxml_html.fromstring(resp.text)
        pager = tree.xpath('//*[contains(concat(" ", @class, " "), " o_pk_pager ")]')
        self.assertTrue(pager)
        labels = [a.get('aria-label') for a in pager[0].xpath('.//a[@aria-label]')]
        self.assertEqual(labels, ['Précédent', 'Suivant'])
        self.assertNotIn('"Previous"', resp.text)

    def test_no_bookings_template_calls_portal_pager(self):
        root = get_module_path('bemade_sports_clinic_bookings')
        offenders = []
        for path in sorted(glob.glob(os.path.join(root, 'views', '*.xml'))):
            with open(path, encoding='utf-8') as handle:
                if 't-call="portal.pager"' in handle.read():
                    offenders.append(os.path.basename(path))
        self.assertFalse(offenders)
