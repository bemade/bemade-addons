# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""Use case: an update is internal, or shared with chosen recipients.

ACCEPTANCE CRITERIA
- Internal only (``internal_only``) is True on a new update, whether created
  from the form or by code. An internal update behaves exactly as in core
  Odoo: no message on the project chatter, no notified partner.
- On the form (driven through ``Form``), unticking Internal only shows the
  recipients (``recipient_ids``), prefilled with the project's followers and
  its portal collaborators, each partner once. They can be edited before
  saving. Ticking it again hides them. Code creating or writing
  ``internal_only=False`` without recipients gets the same prefill.
- Each recipient is emailed ONCE, the first time the update is shared with
  them, by one Discussion message (``mail.mt_comment``) posted on the update
  itself and addressed to those recipients. No project follower who is not
  a recipient is notified. (On the update, not the project: a Discussion on
  the project notifies all its followers, and its messages are readable by
  anyone who can open the project. On the update, reading the message needs
  access to the update.) The message holds the update's title,
  status, date and full description, and a link to the project's portal
  updates page. Its fixed wording (status label, link text) is in the
  project customer's language; the update's own content is sent as written.
  * Saving an update shared, on creation or by unticking Internal only,
    emails all its recipients.
  * Adding recipients to a shared update emails only the added ones.
  * Removing recipients, editing the title, status or description, or
    ticking Internal only sends nothing.
  * Unticking Internal only again later emails only recipients never
    emailed about this update.
- A shared update with no recipients sends nothing and is visible to no
  portal user.
"""
from odoo import Command
from odoo.tests import Form

from .common import ProjectUpdateShareCommon


class TestUpdateSharing(ProjectUpdateShareCommon):
    def _prefill(self):
        return self.follower | self.colleague.partner_id | self.collaborator

    # -- internal by default ---------------------------------------------

    def test_new_update_is_internal_and_sends_nothing(self):
        update = self._update()
        self.assertTrue(update.internal_only)
        self.assertFalse(update.recipient_ids)
        self.assertFalse(self._shares(update))
        self.assertFalse(update.message_ids.notified_partner_ids)
        self.assertFalse(self.project.message_ids.filtered(
            lambda m: m.message_type == "comment"
        ))

    def test_form_untick_prefills_and_tick_hides(self):
        # Opened from the project, as the Updates panel does.
        form = Form(self.Update.with_context(default_project_id=self.project.id))
        form.name = "Week 45"
        self.assertTrue(form.internal_only)
        self.assertTrue(form._get_modifier("recipient_ids", "invisible"))
        form.internal_only = False
        self.assertFalse(form._get_modifier("recipient_ids", "invisible"))
        self.assertEqual(form.recipient_ids[:], self._prefill())
        form.recipient_ids.remove(id=self.colleague.partner_id.id)
        update = form.save()
        self.assertEqual(update.recipient_ids, self.follower | self.collaborator)
        with Form(update) as edit:
            edit.internal_only = True
            self.assertTrue(edit._get_modifier("recipient_ids", "invisible"))

    def test_code_share_without_recipients_gets_prefill(self):
        created = self._update(internal_only=False)
        self.assertEqual(created.recipient_ids, self._prefill())
        written = self._update()
        written.internal_only = False
        self.assertEqual(written.recipient_ids, self._prefill())
        explicit = self._update(
            internal_only=False, recipient_ids=[Command.set(self.follower.ids)],
        )
        self.assertEqual(explicit.recipient_ids, self.follower)

    # -- the email --------------------------------------------------------

    def test_share_on_create_emails_recipients_only(self):
        update = self._update(
            internal_only=False,
            recipient_ids=[Command.set((self.follower | self.collaborator).ids)],
        )
        share = self._shares(update)
        self.assertEqual(len(share), 1)
        self.assertEqual(share.subtype_id, self.mt_comment)
        self.assertEqual(share.partner_ids, self.follower | self.collaborator)
        self.assertEqual(share.notified_partner_ids, self.follower | self.collaborator)
        self.assertNotIn(self.colleague.partner_id, share.notified_partner_ids)
        for text in ("Week 45", "On Track", "Invoices now show tracking.",
                     "/my/projects/%s/updates" % self.project.id):
            self.assertIn(text, str(share.body))
        self.assertFalse(self.project.message_ids.filtered(
            lambda m: m.message_type == "comment"
        ))

    def test_untick_later_emails_all_recipients(self):
        update = self._update()
        update.write({
            "internal_only": False,
            "recipient_ids": [Command.set(self.follower.ids)],
        })
        self.assertEqual(self._shares(update).notified_partner_ids, self.follower)

    def test_added_recipient_alone_is_emailed(self):
        update = self._update(
            internal_only=False, recipient_ids=[Command.set(self.follower.ids)],
        )
        update.recipient_ids = [Command.link(self.collaborator.id)]
        shares = self._shares(update)
        self.assertEqual(len(shares), 2)
        self.assertEqual(shares[1].notified_partner_ids, self.collaborator)

    def test_edits_removals_and_unsharing_send_nothing(self):
        update = self._update(
            internal_only=False,
            recipient_ids=[Command.set((self.follower | self.collaborator).ids)],
        )
        update.write({"name": "Week 45 (rev)", "status": "at_risk",
                      "description": "<p>Changed.</p>"})
        update.recipient_ids = [Command.unlink(self.collaborator.id)]
        update.internal_only = True
        self.assertEqual(len(self._shares(update)), 1)

    def test_reshare_emails_only_new_recipients(self):
        update = self._update(
            internal_only=False, recipient_ids=[Command.set(self.follower.ids)],
        )
        update.internal_only = True
        update.write({
            "internal_only": False,
            "recipient_ids": [Command.link(self.collaborator.id)],
        })
        shares = self._shares(update)
        self.assertEqual(len(shares), 2)
        self.assertEqual(shares[1].notified_partner_ids, self.collaborator)
        update.internal_only = True
        update.internal_only = False
        self.assertEqual(len(self._shares(update)), 2, "everyone already had it")

    def test_shared_without_recipients_sends_nothing(self):
        update = self._update(internal_only=False, recipient_ids=[Command.clear()])
        self.assertFalse(update.internal_only)
        self.assertFalse(update.recipient_ids)
        self.assertFalse(self._shares(update))

    def test_fixed_wording_in_customer_language(self):
        self.env["res.lang"]._activate_lang("fr_CA")
        self.env["ir.module.module"]._load_module_terms(
            ["project_update_share"], ["fr_CA"], overwrite=True,
        )
        self.customer.lang = "fr_CA"
        update = self._update(
            internal_only=False, recipient_ids=[Command.set(self.follower.ids)],
        )
        body = str(self._shares(update).body)
        self.assertIn("Voir toutes les mises à jour du projet", body)
        self.assertIn("Invoices now show tracking.", body, "content as written")
