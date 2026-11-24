Helpdesk bridge of `mail_company_signature`: on the emails written on a
ticket, the signature shows the ticket team's address, whoever writes.

On the helpdesk team form (Configuration > Teams, Email Alias block),
"Signature email address" picks the address (any alias with a domain, for
example `sac@example.com` when the team's own alias is `support@example.com`).
Empty means the team's own alias.

When an internal user writes on a ticket (chatter, full composer, templates
embedding their signature), the personal address in their signature is
replaced by the team address, even when the user has their own "Signature
email address". The sender (From) and Reply-To are not changed.

Left alone:

* messages written by the customer or a portal user;
* tickets without a team, or whose team has no inbox: the user's own
  "Signature email address" rule applies.
