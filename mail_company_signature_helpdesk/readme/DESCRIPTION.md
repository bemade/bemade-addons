Helpdesk bridge of `mail_company_signature`: the emails written on a ticket use
the ticket team's address, whoever writes.

On the helpdesk team form (Configuration > Teams, Email Alias block),
"Sending address" picks the address (any alias with a domain, for example
`sac@example.com` when the team's own alias is `support@example.com`). Empty
means the team's own alias.

A ticket imposes that address (`helpdesk.ticket._mail_sender_override`), so for
an internal user writing on it, even one with their own "Sending address":

* the signature built by `mail_company_signature` (company signature policy)
  shows the team address, in the composer preview and in the email;
* with the company setting « Send from the signature address », the email goes
  out as « Name (Team) » <team address>, Reply-To the team address.

Left alone: messages written by the customer or a portal user, and tickets
without a team or whose team has no inbox (the user's own rule applies).
