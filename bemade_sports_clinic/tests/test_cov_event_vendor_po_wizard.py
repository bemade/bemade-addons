from datetime import datetime

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestCovEventVendorPOWizard(TransactionCase):
    """Coverage for sports.event.vendor.po.wizard (default_get + action_add_to_vendor_po)."""

    COV_PARAM = 'bemade_sports_clinic.product_event_coverage_vendor_id'
    TRV_PARAM = 'bemade_sports_clinic.product_event_travel_vendor_id'
    CLI_PARAM = 'bemade_sports_clinic.product_event_clinic_vendor_id'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ICP = cls.env['ir.config_parameter'].sudo()

        cls.org = cls.env['res.partner'].create({'name': 'PO Org', 'is_company': True})
        cls.team = cls.env['sports.team'].create({'name': 'PO Team', 'parent_id': cls.org.id})
        cls.venue = cls.env['res.partner'].create({'name': 'PO Arena', 'is_venue': True})

        # Therapist users -> their partners become the vendor on the PO.
        cls.therapist = cls.env['res.users'].create({
            'name': 'Therapist One', 'login': 'cov_po_therapist1', 'email': 'cov_po_t1@example.com',
        })
        cls.therapist2 = cls.env['res.users'].create({
            'name': 'Therapist Two', 'login': 'cov_po_therapist2', 'email': 'cov_po_t2@example.com',
        })

        # Standard (non-clinic) event + a clinic event.
        cls.event = cls.env['sports.event'].create({
            'name': 'Coverage Game',
            'event_type': 'game',
            'team_ids': [Command.set([cls.team.id])],
            'venue_id': cls.venue.id,
            'date_start': datetime(2026, 1, 5, 10, 0),
            'date_end': datetime(2026, 1, 5, 12, 0),
            'state': 'confirmed',
        })
        cls.clinic_event = cls.env['sports.event'].create({
            'name': 'Coverage Clinic',
            'event_type': 'clinic',
            'date_start': datetime(2026, 1, 6, 10, 0),
            'date_end': datetime(2026, 1, 6, 12, 0),
            'state': 'confirmed',
        })

        # Vendor products used by the wizard (referenced via ir.config_parameter).
        cls.prod_cov = cls.env['product.product'].create({'name': 'Coverage (Vendor)'})
        cls.prod_trv = cls.env['product.product'].create({'name': 'Travel (Vendor)'})
        cls.prod_cli = cls.env['product.product'].create({'name': 'Clinic (Vendor)'})

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _clear_products(self):
        """Make all three vendor-product params resolve to an empty recordset."""
        self.ICP.set_param(self.COV_PARAM, '0')
        self.ICP.set_param(self.TRV_PARAM, '0')
        self.ICP.set_param(self.CLI_PARAM, '0')

    def _set_products(self):
        self.ICP.set_param(self.COV_PARAM, str(self.prod_cov.id))
        self.ICP.set_param(self.TRV_PARAM, str(self.prod_trv.id))
        self.ICP.set_param(self.CLI_PARAM, str(self.prod_cli.id))

    def _timesheet(self, event=None, user=None, coverage=True, travel=False):
        """Create a timesheet; coverage_duration/travel_duration are computed from times."""
        event = event or self.event
        user = user or self.therapist
        vals = {'event_id': event.id, 'user_id': user.id}
        if coverage:
            vals['coverage_start'] = datetime(2026, 1, 5, 10, 0)
            vals['coverage_end'] = datetime(2026, 1, 5, 12, 0)  # 2h coverage
        if travel:
            vals['travel_start'] = datetime(2026, 1, 5, 9, 0)   # 1h before
            vals['travel_end'] = datetime(2026, 1, 5, 13, 0)    # 1h after
        return self.env['sports.event.timesheet'].create(vals)

    def _wizard(self, timesheet_ids, **vals):
        """default_get pulls from the active context, so create through it."""
        return self.env['sports.event.vendor.po.wizard'].with_context(
            active_model='sports.event.timesheet',
            active_ids=timesheet_ids,
        ).create(vals)

    # ------------------------------------------------------------------
    # default_get
    # ------------------------------------------------------------------

    @mute_logger('odoo.addons.bemade_sports_clinic.models.event_vendor_po_wizard')
    def test_default_get_wrong_active_model_raises(self):
        with self.assertRaises(UserError):
            self.env['sports.event.vendor.po.wizard'].with_context(
                active_model='sports.event', active_ids=[self.event.id],
            ).create({})

    @mute_logger('odoo.addons.bemade_sports_clinic.models.event_vendor_po_wizard')
    def test_default_get_no_timesheets_raises(self):
        with self.assertRaises(UserError):
            self.env['sports.event.vendor.po.wizard'].with_context(
                active_model='sports.event.timesheet', active_ids=[],
            ).create({})

    @mute_logger('odoo.addons.bemade_sports_clinic.models.event_vendor_po_wizard')
    def test_default_get_multiple_therapists_raises(self):
        ts1 = self._timesheet(user=self.therapist)
        ts2 = self._timesheet(user=self.therapist2)
        with self.assertRaises(UserError):
            self._wizard([ts1.id, ts2.id])

    def test_default_get_prefills_single_therapist(self):
        ts = self._timesheet()
        wizard = self._wizard([ts.id])
        self.assertEqual(wizard.therapist_partner_id, self.therapist.partner_id)
        self.assertIn(ts, wizard.timesheet_ids)

    def test_default_get_prefills_existing_draft_po(self):
        ts = self._timesheet()
        po = self.env['purchase.order'].create({'partner_id': self.therapist.partner_id.id})
        wizard = self._wizard([ts.id])
        self.assertEqual(wizard.purchase_order_id, po,
                         "An open draft PO for the therapist should be pre-selected")

    # ------------------------------------------------------------------
    # action_add_to_vendor_po — guard branches
    # ------------------------------------------------------------------

    @mute_logger('odoo.addons.bemade_sports_clinic.models.event_vendor_po_wizard')
    def test_action_requires_timesheets(self):
        ts = self._timesheet()
        wizard = self._wizard([ts.id])
        wizard.timesheet_ids = [Command.clear()]
        with self.assertRaises(UserError):
            wizard.action_add_to_vendor_po()

    @mute_logger('odoo.addons.bemade_sports_clinic.models.event_vendor_po_wizard')
    def test_action_missing_coverage_product_raises(self):
        self._clear_products()
        ts = self._timesheet()
        wizard = self._wizard([ts.id])
        with self.assertRaises(UserError):
            wizard.action_add_to_vendor_po()

    @mute_logger('odoo.addons.bemade_sports_clinic.models.event_vendor_po_wizard')
    def test_action_missing_travel_product_raises(self):
        # Coverage configured, travel missing -> raises on the travel product check.
        self.ICP.set_param(self.COV_PARAM, str(self.prod_cov.id))
        self.ICP.set_param(self.TRV_PARAM, '0')
        self.ICP.set_param(self.CLI_PARAM, '0')
        ts = self._timesheet()
        wizard = self._wizard([ts.id])
        with self.assertRaises(UserError):
            wizard.action_add_to_vendor_po()

    @mute_logger('odoo.addons.bemade_sports_clinic.models.event_vendor_po_wizard')
    def test_ensure_po_no_select_no_create_raises(self):
        self._set_products()
        ts = self._timesheet()
        wizard = self._wizard([ts.id])
        wizard.write({'purchase_order_id': False, 'create_new_if_missing': False})
        with self.assertRaises(UserError):
            wizard.action_add_to_vendor_po()

    @mute_logger('odoo.addons.bemade_sports_clinic.models.event_vendor_po_wizard')
    def test_action_no_lines_created_raises(self):
        # A timesheet already linked to PO lines yields nothing on a second run.
        self._set_products()
        ts = self._timesheet(coverage=True, travel=True)
        wizard = self._wizard([ts.id])
        wizard.create_new_if_missing = True
        wizard.action_add_to_vendor_po()  # first run links coverage + travel lines

        wizard2 = self._wizard([ts.id])
        wizard2.create_new_if_missing = True
        with self.assertRaises(UserError):
            wizard2.action_add_to_vendor_po()

    @mute_logger('odoo.addons.bemade_sports_clinic.models.event_vendor_po_wizard')
    def test_action_clinic_event_rejects_travel(self):
        self._set_products()
        ts = self._timesheet(event=self.clinic_event, coverage=True, travel=True)
        wizard = self._wizard([ts.id])
        with self.assertRaises(UserError):
            wizard.action_add_to_vendor_po()

    # ------------------------------------------------------------------
    # action_add_to_vendor_po — success paths
    # ------------------------------------------------------------------

    def test_action_standard_event_creates_coverage_and_travel_lines(self):
        self._set_products()
        ts = self._timesheet(coverage=True, travel=True)
        wizard = self._wizard([ts.id])
        wizard.create_new_if_missing = True

        result = wizard.action_add_to_vendor_po()

        self.assertTrue(ts.vendor_purchase_order_id, "timesheet should be linked to a PO")
        po = ts.vendor_purchase_order_id
        self.assertEqual(ts.purchase_coverage_line_id.order_id, po)
        self.assertEqual(ts.purchase_travel_line_id.order_id, po)
        self.assertEqual(len(po.order_line), 2, "coverage + travel lines expected")
        self.assertEqual(result.get('res_id'), po.id)

    def test_action_clinic_event_creates_clinic_line(self):
        self._set_products()
        ts = self._timesheet(event=self.clinic_event, coverage=True, travel=False)
        wizard = self._wizard([ts.id])
        wizard.create_new_if_missing = True

        wizard.action_add_to_vendor_po()

        po = ts.vendor_purchase_order_id
        self.assertTrue(po, "clinic timesheet should be linked to a PO")
        self.assertEqual(len(po.order_line), 1, "single clinic line expected")
        self.assertEqual(po.order_line.product_id, self.prod_cli)

    def test_action_uses_selected_existing_po(self):
        self._set_products()
        ts = self._timesheet(coverage=True, travel=False)
        po = self.env['purchase.order'].create({'partner_id': self.therapist.partner_id.id})
        wizard = self._wizard([ts.id])
        wizard.purchase_order_id = po

        wizard.action_add_to_vendor_po()

        self.assertEqual(ts.vendor_purchase_order_id, po,
                         "the pre-selected PO should be reused, not recreated")
        self.assertEqual(len(po.order_line), 1)
