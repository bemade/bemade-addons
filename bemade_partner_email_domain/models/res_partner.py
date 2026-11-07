import re

from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import email_normalize

SUGGEST_ONLY_PARAM = "bemade_partner_email_domain.suggest_only"

# Public mailbox providers: a company can never own one of these domains.
PUBLIC_MAIL_DOMAINS = frozenset(
    {
        "aol.com",
        "bell.net",
        "cogeco.ca",
        "gmail.com",
        "gmx.com",
        "googlemail.com",
        "hotmail.ca",
        "hotmail.com",
        "hotmail.fr",
        "icloud.com",
        "live.ca",
        "live.com",
        "live.fr",
        "mac.com",
        "me.com",
        "msn.com",
        "outlook.com",
        "outlook.fr",
        "proton.me",
        "protonmail.com",
        "rogers.com",
        "shaw.ca",
        "sympatico.ca",
        "telus.net",
        "videotron.ca",
        "videotron.qc.ca",
        "yahoo.ca",
        "yahoo.com",
        "yahoo.fr",
    }
)

# Labels of letters (internationalised ones included), digits and inner dashes.
_LABEL = r"[^\W_](?:[^\W_]|-)*(?<!-)"
_DOMAIN_RE = re.compile(rf"^{_LABEL}(?:\.{_LABEL})+$")


def normalize_email_domain(value):
    """Lowercase and strip a configured email domain (no other rewriting)."""
    return (value or "").strip().lower()


def email_domain_error(value):
    """Return why ``value`` is not a valid company email domain (a code), or None."""
    if "@" in value:
        return "at_sign"
    if "/" in value or ":" in value:
        return "url"
    if "." not in value:
        return "no_dot"
    if not _DOMAIN_RE.match(value):
        return "characters"
    if value in PUBLIC_MAIL_DOMAINS:
        return "public"
    return None


def email_domain_of(email):
    """Domain part of the first address in ``email``, lowercased, or ''."""
    normalized = email_normalize(email or "", strict=False)
    if not normalized or "@" not in normalized:
        return ""
    return normalized.rsplit("@", 1)[1].strip().lower()


def domain_suffixes(domain):
    """Label-boundary suffixes of ``domain``, most specific first.

    ``a.b.example.com`` -> [a.b.example.com, b.example.com, example.com]
    (the bare top-level label is never a candidate).
    """
    labels = [label for label in domain.split(".") if label]
    return [".".join(labels[i:]) for i in range(len(labels) - 1)]


def is_anchored_match(email_domain, configured):
    """True when ``configured`` matches ``email_domain`` on a label boundary."""
    return email_domain == configured or email_domain.endswith("." + configured)


class ResPartner(models.Model):
    _inherit = "res.partner"

    email_domain = fields.Char(
        help="Email domain owned by this company (e.g. example.com). New contacts "
        "whose email ends with this domain are attached to this company.",
    )
    is_subdivision = fields.Boolean(string="Subdivision", default=False)
    parent_set_by_email_domain = fields.Boolean(
        string="Attached by Email Domain",
        copy=False,
        readonly=True,
        help="The company of this contact was set automatically from its email "
        "domain. Use Detach to undo it.",
    )
    parent_suggestion_ids = fields.One2many(
        "partner.parent.suggestion", "partner_id", string="Company Suggestions"
    )

    # ------------------------------------------------------------------
    # Email domain validation
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("email_domain"):
                vals["email_domain"] = normalize_email_domain(vals["email_domain"])
        partners = super().create(vals_list)
        if not self.env.context.get("skip_email_domain_match"):
            partners._match_parent_from_email_domain(source="create")
        return partners

    def write(self, vals):
        if vals.get("email_domain"):
            vals = dict(vals, email_domain=normalize_email_domain(vals["email_domain"]))
        if "parent_id" in vals and not self.env.context.get("email_domain_auto_parent"):
            vals = dict(vals, parent_set_by_email_domain=False)
        res = super().write(vals)
        if vals.get("parent_id"):
            # A contact that got a company by any means leaves the triage list.
            self.env["partner.parent.suggestion"].sudo().search(
                [("partner_id", "in", self.ids)]
            ).unlink()
        if "email" in vals and not self.env.context.get("skip_email_domain_match"):
            self._match_parent_from_email_domain(source="email")
        return res

    def _email_domain_error_message(self, code):
        messages = {
            "at_sign": self.env._(
                "an email domain must not contain '@' (use example.com, not name@example.com)"
            ),
            "url": self.env._(
                "an email domain must not contain a scheme or a path (use example.com, not https://example.com/)"
            ),
            "no_dot": self.env._("an email domain must contain at least one dot"),
            "characters": self.env._("an email domain may only contain letters, digits, dashes and dots"),
            "public": self.env._("this is a public mailbox provider, it cannot identify a company"),
        }
        return messages[code]

    @api.constrains("email_domain")
    def _check_email_domain(self):
        for partner in self:
            if not partner.email_domain:
                continue
            code = email_domain_error(partner.email_domain)
            if code:
                raise ValidationError(
                    self.env._(
                        "Invalid email domain %(domain)s: %(error)s",
                        domain=partner.email_domain,
                        error=partner._email_domain_error_message(code),
                    )
                )

    @api.onchange("is_subdivision")
    def _onchange_is_subdivision(self):
        """A subdivision is not a plain contact: contacts of type "contact" get
        their address overwritten by their parent's."""
        for partner in self:
            if partner.is_subdivision and partner.type == "contact":
                partner.type = "other"

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------

    def _is_email_domain_match_target(self):
        self.ensure_one()
        return (
            not self.is_company
            and not self.parent_id
            and self.type == "contact"
            and bool(self.email)
        )

    @api.model
    def _find_email_domain_candidates(self, email_domain):
        """Companies whose configured domain matches ``email_domain``.

        Anchored on a label boundary; only the most specific matching level is
        returned (several companies when they share that same domain).
        """
        if not email_domain:
            return self.browse()
        suffixes = domain_suffixes(email_domain)
        if not suffixes:
            return self.browse()
        company_ids = [False, self.env.company.id]
        # Configured values may still carry legacy capitals: compare
        # case-insensitively (=ilike without wildcards, escaped).
        ilike_domain = []
        for suffix in suffixes:
            escaped = suffix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            ilike_domain = (["|"] + ilike_domain if ilike_domain else []) + [("email_domain", "=ilike", escaped)]
        companies = (
            self.sudo()
            .with_context(active_test=True)
            .search(
                [("is_company", "=", True), ("company_id", "in", company_ids)] + ilike_domain,
                order="id",
            )
        )
        for suffix in suffixes:
            level = companies.filtered(lambda c, s=suffix: normalize_email_domain(c.email_domain) == s)
            if level:
                return level.with_env(self.env)
        return self.browse()

    def _match_parent_from_email_domain(self, source):
        suggest_only = self._email_domain_suggest_only()
        Suggestion = self.env["partner.parent.suggestion"].sudo()
        for partner in self:
            if not partner._is_email_domain_match_target():
                continue
            email_domain = email_domain_of(partner.email)
            candidates = self._find_email_domain_candidates(email_domain)
            if not candidates:
                if source == "email":
                    # The new address no longer matches: drop a stale row.
                    Suggestion.search(
                        [("partner_id", "=", partner.id), ("source", "in", ("create", "email", "backfill"))]
                    ).unlink()
                continue
            if len(candidates) == 1 and not suggest_only:
                partner._attach_to_email_domain_parent(candidates, email_domain)
            else:
                Suggestion._queue(partner, candidates, email_domain, source)

    @api.model
    def _email_domain_suggest_only(self):
        return bool(self.env["ir.config_parameter"].sudo().get_param(SUGGEST_ONLY_PARAM))

    def _attach_to_email_domain_parent(self, company, email_domain):
        self.ensure_one()
        self.with_context(email_domain_auto_parent=True).write(
            {"parent_id": company.id, "parent_set_by_email_domain": True}
        )
        self._post_email_domain_note(
            Markup("Rattaché à %s par le domaine de courriel <b>%s</b>.<br/>Attached to %s by email domain <b>%s</b>.")
            % (company.display_name, email_domain, company.display_name, email_domain)
        )

    def _post_email_domain_note(self, body):
        self.ensure_one()
        self.sudo().message_post(
            body=body,
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )

    def action_detach_email_domain_parent(self):
        for partner in self:
            if not partner.parent_id:
                continue
            company = partner.parent_id
            partner.write({"parent_id": False})
            partner._post_email_domain_note(
                Markup("Détaché de %s.<br/>Detached from %s.") % (company.display_name, company.display_name)
            )
        return True

    # ------------------------------------------------------------------
    # Migration helpers (19.0.1.0.0) - also used by the tests
    # ------------------------------------------------------------------

    @api.model
    def _email_domain_suffix_mismatches(self):
        """Contacts whose current parent's email domain is only a bare suffix
        of their own email domain (``lantic.ca`` for ``@atlantic.ca``): the
        unanchored matcher of the previous versions attached them."""
        self.env.cr.execute(
            """
            SELECT c.id, c.email, p.email_domain
              FROM res_partner c
              JOIN res_partner p ON p.id = c.parent_id
             WHERE c.is_company IS NOT TRUE
               AND c.email LIKE '%%@%%'
               AND COALESCE(TRIM(p.email_domain), '') <> ''
            """
        )
        ids = []
        for partner_id, email, configured in self.env.cr.fetchall():
            email_domain = email_domain_of(email)
            configured = normalize_email_domain(configured)
            if (
                email_domain
                and email_domain.endswith(configured)
                and not is_anchored_match(email_domain, configured)
            ):
                ids.append(partner_id)
        return self.with_context(active_test=False).browse(ids)

    def _email_domain_detach_and_queue(self):
        """Detach wrongly suffix-matched contacts and queue them for triage."""
        Suggestion = self.env["partner.parent.suggestion"].sudo()
        for partner in self:
            company = partner.parent_id
            partner.with_context(skip_email_domain_match=True).write({"parent_id": False})
            partner._post_email_domain_note(
                Markup(
                    "Détaché de %s : le domaine de courriel de l'entreprise (%s) ne correspondait "
                    "qu'à la fin du domaine du contact. À rattacher dans « Contacts non assignés »."
                    "<br/>Detached from %s: the company's email domain (%s) only matched the end of the "
                    "contact's domain. To be assigned in \"Unassigned contacts\"."
                )
                % (company.display_name, company.email_domain, company.display_name, company.email_domain)
            )
            email_domain = email_domain_of(partner.email)
            candidates = self._find_email_domain_candidates(email_domain)
            Suggestion._queue(partner, candidates, email_domain, "suffix_fix")

    def _email_domain_backfill(self):
        """Re-match contacts left without company by the former email flow.

        Same rule as a new contact: a single candidate attaches the contact
        (flag, note, Detach available) unless "suggest only" is set; two or
        more candidates queue it in Unassigned contacts. Returns the
        ``(attached, queued)`` recordsets.
        """
        suggest_only = self._email_domain_suggest_only()
        Suggestion = self.env["partner.parent.suggestion"].sudo()
        attached = queued = self.browse()
        for partner in self:
            if not partner.active or not partner._is_email_domain_match_target():
                continue
            email_domain = email_domain_of(partner.email)
            candidates = self._find_email_domain_candidates(email_domain)
            if not candidates:
                continue
            if len(candidates) == 1 and not suggest_only:
                partner._attach_to_email_domain_parent(candidates, email_domain)
                attached |= partner
            else:
                Suggestion._queue(partner, candidates, email_domain, "backfill")
                queued |= partner
        return attached, queued
