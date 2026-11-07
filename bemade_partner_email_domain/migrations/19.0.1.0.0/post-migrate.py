"""19.0.1.0.0: anchored matching, no outbound email, triage list.

1. Contacts that the former unanchored matcher attached to a company whose
   email domain is only a bare suffix of theirs (``lantic.ca`` for
   ``@atlantic.ca``) are detached, noted and queued in Unassigned contacts.
2. Contacts left without a company by the former "select your division"
   email (they carry an access token) are re-matched with the anchored rule
   and queued when at least one company matches. Nothing is attached here.
3. The access tokens are cleared and their column dropped; the email
   template is deleted (it was noupdate, so the upgrade would keep it).
4. Malformed and bare-suffix configured email domains are logged for a
   manual clean-up.
"""

import logging

from odoo import SUPERUSER_ID, api

from odoo.addons.bemade_partner_email_domain.models.res_partner import (
    email_domain_error,
    is_anchored_match,
    normalize_email_domain,
)

_logger = logging.getLogger(__name__)


def _column_exists(cr, table, column):
    cr.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
        (table, column),
    )
    return bool(cr.fetchone())


def _log_configured_domain_issues(cr):
    cr.execute(
        """
        SELECT id, email_domain, is_company, active
          FROM res_partner
         WHERE COALESCE(TRIM(email_domain), '') <> ''
         ORDER BY id
        """
    )
    rows = cr.fetchall()
    malformed = []
    for partner_id, value, is_company, active in rows:
        stripped = value.strip()
        if stripped != value or stripped.lower() != stripped or email_domain_error(stripped):
            malformed.append((partner_id, value, is_company, active))
    _logger.warning("email domain: %s malformed configured values (id, value, is_company, active): %s",
                    len(malformed), malformed)
    active_companies = {}
    for partner_id, value, is_company, active in rows:
        if is_company and active:
            active_companies.setdefault(normalize_email_domain(value), []).append(partner_id)
    bare = []
    for short, short_ids in active_companies.items():
        for long_, long_ids in active_companies.items():
            if long_ != short and long_.endswith(short) and not is_anchored_match(long_, short):
                bare.append((short, short_ids, long_, long_ids))
    _logger.warning("email domain: %s bare-suffix pairs among active companies (short, ids, long, ids): %s",
                    len(bare), bare)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {"active_test": False})
    Partner = env["res.partner"]

    token_ids = []
    if _column_exists(cr, "res_partner", "access_token"):
        cr.execute("SELECT id FROM res_partner WHERE access_token IS NOT NULL")
        token_ids = [r[0] for r in cr.fetchall()]
    token_partners = Partner.browse(token_ids)
    without_parent = token_partners.filtered(lambda p: not p.parent_id)

    # 1. Wrong suffix matches
    mismatches = Partner._email_domain_suffix_mismatches()
    _logger.warning(
        "email domain: detaching %s contacts attached by a bare domain suffix (contact id, former parent id): %s",
        len(mismatches),
        [(p.id, p.parent_id.id) for p in mismatches],
    )
    mismatches._email_domain_detach_and_queue()

    # 2. Contacts left behind by the former division email (selected before
    #    step 1 changes any parent)
    queued = without_parent._email_domain_queue_backfill()
    _logger.warning(
        "email domain: %s partners had an access token, %s without company, %s queued in Unassigned contacts",
        len(token_partners), len(without_parent), len(queued),
    )

    # 3. Tokens and email template
    if token_ids:
        cr.execute("UPDATE res_partner SET access_token = NULL WHERE access_token IS NOT NULL")
    if _column_exists(cr, "res_partner", "access_token"):
        cr.execute("ALTER TABLE res_partner DROP COLUMN access_token")
    template = env.ref("bemade_partner_email_domain.email_template_select_parent", raise_if_not_found=False)
    if template:
        template.unlink()
        _logger.warning("email domain: deleted the 'select your division' email template")

    # 4. Report configured values that need a manual fix
    _log_configured_domain_issues(cr)
