Helpdesk bridge of `mail_company_signature`: every email written on a ticket
goes out from the ticket team's inbox, whoever writes it.

On the helpdesk team form (Configuration > Teams, Email Alias block), "Send
as" picks the team inbox (any alias with a domain, for example
`sac@example.com` when the team's own alias is `support@example.com`). Empty
means the team's own alias.

When an internal user writes on a ticket (chatter, full composer, templates
whose sender is the user's own address), the email goes out as
"User Name (Team Name)" <team inbox>, with Reply-To the team inbox, even
when the user has their own "Send emails as" set. Replies thread back onto
the ticket.

Left alone:

* messages written by the customer or a portal user, and by OdooBot;
* emails whose sender is another fixed address (a template sending from
  `finance@...`, for example);
* tickets without a team, or whose team has no inbox: the user's own
  "Send emails as" rule applies.
