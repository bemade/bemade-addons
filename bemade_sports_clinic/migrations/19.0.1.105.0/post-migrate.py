"""Task 1639 — the internal « Treatment Professional » group implies the
clinic « Internal User » group. The group record is noupdate, so the new
implication is written here for existing databases (a fresh install gets it
from security/sports_clinic_groups.xml). Idempotent; logs counts only."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    tp_group = env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional', raise_if_not_found=False)
    clinic_user = env.ref('bemade_sports_clinic.group_sports_clinic_user', raise_if_not_found=False)
    if not tp_group or not clinic_user:
        return
    before = clinic_user in tp_group.implied_ids
    trapped = env['res.users'].with_context(active_test=False).search([
        ('group_ids', 'in', tp_group.id), ('share', '=', False)]).filtered(
        lambda user: clinic_user not in user.all_group_ids)
    if not before:
        tp_group.write({'implied_ids': [(4, clinic_user.id)]})
    _logger.info(
        "Task 1639: Treatment Professional implies Internal User (%s); %d internal therapist(s) "
        "lacked the clinic user group before", 'already' if before else 'added', len(trapped))
