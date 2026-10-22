"""Security hotfix 19.0.1.42.5 — narrow the portal injury-document rule.

``portal_injury_document_access`` lives in a ``noupdate`` block, so an upgrade
does not refresh its domain from the XML. Rewrite it here so portal users
(coaches, role « other » staff) stop reading documents of injuries flagged
``hidden_from_coaches``. Portal treatment professionals keep them through the
new non-noupdate rule ``portal_treatment_professional_injury_document_access``.

Keep NEW_DOMAIN identical to the XML in security/sports_clinic_portal_rules.xml.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

NEW_DOMAIN = (
    "[('patient_id.team_ids.staff_ids.user_ids', 'in', user.id), '|', "
    "('injury_id', '=', False), ('injury_id.hidden_from_coaches', '=', False)]"
)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    rule = env.ref(
        'bemade_sports_clinic.portal_injury_document_access',
        raise_if_not_found=False,
    )
    if not rule:
        _logger.warning("portal_injury_document_access not found; nothing to rewrite")
        return
    if rule.domain_force != NEW_DOMAIN:
        rule.write({'domain_force': NEW_DOMAIN})
        _logger.info("portal_injury_document_access domain rewritten (hidden injuries excluded)")
