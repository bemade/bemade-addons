"""Task 1727, review round 1 (owner 2026-10-27): the backend flags a past
« Retour prévu » too. Synthetic fixtures only.

* UC-B1 Compute: ``predicted_return_overdue`` is True when
  ``predicted_return_date`` is before today in the user's timezone (today,
  a future date or no date: False). Non-stored.
* UC-B2 Search: the field is searchable (``= True`` / ``= False`` /
  ``!= True``), so the patient search view offers a « Retour prévu
  dépassé » filter returning exactly the overdue players.
* UC-B3 Player lists (``sports_patient_view_list`` and
  ``sports_patient_view_list_embedded``): a past « Retour prévu » cell is
  highlighted (``decoration-warning`` on the date column).
* UC-B4 Player form: next to « Retour prévu » a warning badge « Dépassé »
  shows only when the date has passed.
* UC-B5 French: the filter and the badge render in fr_CA (« Retour prévu
  dépassé », « Dépassé »).
"""
from datetime import timedelta

from lxml import etree

from odoo import fields
from odoo.tests import Form, TransactionCase, tagged

from odoo.addons.bemade_sports_clinic.models.patient import PAST_RETURN_OK


@tagged('post_install', '-at_install')
class TestRetourPrevuBackend1727(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Patient = cls.env['sports.patient'].with_context(**{PAST_RETURN_OK: True})
        today = fields.Date.context_today(cls.Patient)
        cls.past = cls.Patient.create({'first_name': 'Overdue', 'last_name': 'Synthetic1727',
                                       'predicted_return_date': today - timedelta(days=2)})
        cls.today_p = cls.Patient.create({'first_name': 'Today', 'last_name': 'Synthetic1727',
                                          'predicted_return_date': today})
        cls.future = cls.Patient.create({'first_name': 'Future', 'last_name': 'Synthetic1727',
                                         'predicted_return_date': today + timedelta(days=9)})
        cls.blank = cls.Patient.create({'first_name': 'Blank', 'last_name': 'Synthetic1727'})
        cls.all = cls.past | cls.today_p | cls.future | cls.blank

    def _search(self, domain):
        return self.env['sports.patient'].search([('last_name', '=', 'Synthetic1727')] + domain)

    # UC-B1
    def test_compute(self):
        self.assertEqual(self.all.filtered('predicted_return_overdue'), self.past)
        self.assertFalse(self.env['sports.patient']._fields['predicted_return_overdue'].store)

    # UC-B2
    def test_search(self):
        self.assertEqual(self._search([('predicted_return_overdue', '=', True)]), self.past)
        self.assertEqual(self._search([('predicted_return_overdue', '=', False)]), self.all - self.past)
        self.assertEqual(self._search([('predicted_return_overdue', '!=', True)]), self.all - self.past)
        self.assertEqual(self._search([('predicted_return_overdue', '!=', False)]), self.past)

    def test_search_view_filter(self):
        arch = self.env['sports.patient'].get_view(
            self.env.ref('bemade_sports_clinic.sports_patient_view_search').id, 'search')['arch']
        [flt] = etree.fromstring(arch).xpath("//filter[@name='predicted_return_overdue']")
        self.assertEqual(flt.get('string'), 'Predicted Return Overdue')
        domain = eval(flt.get('domain'))  # noqa: S307 - static view domain
        self.assertEqual(self._search(domain), self.past)

    # UC-B3
    def test_list_views_highlight(self):
        for xmlid in ('sports_patient_view_list', 'sports_patient_view_list_embedded'):
            view = self.env.ref(f'bemade_sports_clinic.{xmlid}')
            arch = etree.fromstring(self.env['sports.patient'].get_view(view.id, 'list')['arch'])
            [cell] = arch.xpath("//field[@name='predicted_return_date']")
            self.assertEqual(cell.get('decoration-warning'), 'predicted_return_overdue', xmlid)
            self.assertTrue(arch.xpath("//field[@name='predicted_return_overdue']"), xmlid)

    # UC-B4
    def test_form_badge(self):
        view = self.env.ref('bemade_sports_clinic.sports_patient_view_form')
        arch = etree.fromstring(self.env['sports.patient'].get_view(view.id, 'form')['arch'])
        [badge] = arch.xpath("//span[hasclass('o_sc_overdue_badge')]")
        self.assertIn('text-bg-warning', badge.get('class'))
        self.assertEqual(badge.get('invisible'), 'not predicted_return_overdue')
        self.assertEqual(badge.text.strip(), 'Passed')
        # The form opens with the flag loaded (overdue and not).
        with Form(self.past, view=view) as form:
            self.assertTrue(form.predicted_return_overdue)
        with Form(self.future, view=view) as form:
            self.assertFalse(form.predicted_return_overdue)

    # UC-B5
    def test_french(self):
        self.env['res.lang']._activate_lang('fr_CA')
        self.env['ir.module.module']._load_module_terms(['bemade_sports_clinic'], ['fr_CA'], overwrite=True)
        Patient = self.env['sports.patient'].with_context(lang='fr_CA')
        form = Patient.get_view(self.env.ref('bemade_sports_clinic.sports_patient_view_form').id, 'form')
        [badge] = etree.fromstring(form['arch']).xpath("//span[hasclass('o_sc_overdue_badge')]")
        self.assertEqual(badge.text.strip(), 'Dépassé')
        search = Patient.get_view(self.env.ref('bemade_sports_clinic.sports_patient_view_search').id, 'search')
        [flt] = etree.fromstring(search['arch']).xpath("//filter[@name='predicted_return_overdue']")
        self.assertEqual(flt.get('string'), 'Retour prévu dépassé')
