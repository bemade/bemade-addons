import logging

from odoo import models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Core refuses to merge more than this many contacts in one call.
CORE_MAX_MERGE = 3


class BasePartnerMergeAutomaticWizard(models.TransientModel):
    _inherit = "base.partner.merge.automatic.wizard"

    def _merge(self, partner_ids, dst_partner=None, extra_checks=True):
        """Merge more than 3 contacts as successive core merges of at most 3.

        Every batch is ``[destination] + 2 sources`` merged by ``super()``, so
        all checks of core and of other modules keep running on each batch.
        Core's own checks are also run once on the whole set first, so that
        splitting the set into batches cannot dodge them. All batches run in
        the caller's transaction: an error in any of them cancels the merge.
        """
        partners = self.env["res.partner"].browse(partner_ids).exists()
        if len(partners) <= CORE_MAX_MERGE:
            return super()._merge(
                partner_ids, dst_partner=dst_partner, extra_checks=extra_checks
            )

        self._check_merge_whole_set(partners, extra_checks=extra_checks)

        # Same destination choice as core.
        if dst_partner and dst_partner in partners:
            src_partners = partners - dst_partner
        else:
            ordered = self._get_ordered_partner(partners.ids)
            dst_partner = ordered[-1]
            src_partners = ordered[:-1]

        step = CORE_MAX_MERGE - 1
        _logger.info(
            "Merging %s contacts into %s in batches of %s",
            len(src_partners), dst_partner.id, step,
        )
        for start in range(0, len(src_partners), step):
            batch = src_partners[start:start + step]
            super()._merge(
                [dst_partner.id] + batch.ids,
                dst_partner=dst_partner,
                extra_checks=extra_checks,
            )

    def _check_merge_whole_set(self, partners, extra_checks=True):
        """Core's safety checks of ``_merge``, run on the complete set."""
        if self.env.is_admin():
            extra_checks = False

        Partner = self.env["res.partner"]
        # A partner of the set must not descend from another partner of it.
        for partner in partners:
            descendants = Partner.search([("id", "child_of", partner.id)]) - partner
            if descendants & partners:
                raise UserError(
                    self.env._("You cannot merge a contact with one of his parent.")
                )

        if len(partners.with_context(active_test=False).user_ids) > 1:
            raise UserError(self.env._(
                "You cannot merge contacts linked to more than one user even if "
                "only one is active."
            ))

        if extra_checks and len({partner.email for partner in partners}) > 1:
            raise UserError(self.env._(
                "All contacts must have the same email. Only the Administrator "
                "can merge contacts with different emails."
            ))
