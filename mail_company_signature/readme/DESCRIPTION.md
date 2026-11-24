Company-standard email signature.

Per company (Settings > Emails), an administrator can enforce one signature
template. While enforced, the signature of every internal user of that company
who has an active employee record in it is generated from the template and that
employee record, and cannot be edited. Users without an employee record, portal
users and companies without the policy are unaffected. Creating or linking an
employee for a user subjects them to the policy (their personal signature is
backed up); unlinking, archiving or deleting it releases them like turning the
policy off.

Template placeholders (`{{...}}`): `name`, `job_title`, `job_position`,
`work_phone`, `mobile_phone`, `work_email`, `company_name`, `company_phone`,
`company_email`, `company_website`, `company_notice`. Unknown placeholders are
left as typed.

* `job_position` shows the employee's job position in French and English,
  "FR / EN" (one value when both names are equal or the French translation is
  missing); without a job position, the employee's job title. `job_title` is
  the job title as typed on the employee.
* `company_notice` is a temporary rich-text notice set per company, with an
  optional "Show until" date. A daily scheduled action removes it once that day
  has passed.

`mobile_phone` is the employee's work mobile only when "Show cell phone in
email signature" is ticked on the employee (default: not ticked, so the cell
line is hidden). HR sets it on the employee form, next to the work mobile; each
user can also tick or untick it for themselves in their preferences (My
Profile), without HR rights. The signature is regenerated at once.

Write one optional line per paragraph: a paragraph whose placeholders are all
empty (for example a user without a mobile phone) is removed entirely, label
included. A paragraph mixing empty and non-empty placeholders is kept.

An administrator can exempt a user ("Manage own signature" on the user
form): that user writes their own signature again. Unticking it regenerates
the signature (the personal one is kept as backup).

The signatures are regenerated when the employee (name, phones, "Show cell
phone in email signature", email, job position or title, also on its current
version), the job position (including its French name), the template, the
notice or the company changes.

The generated signature is written to `res.users.signature`, so every
existing consumer (chatter email, full composer, templates) uses it unchanged.
The inline chatter composer shows a read-only preview of the signature with a
one-click "Remove signature" toggle for the current message.

Send emails as a team inbox
---------------------------

"Send emails as" on the user form (Settings > Users, next to the signature)
picks a team inbox: any email alias with a domain, for example the
`purchasing@` alias of a helpdesk team. When it is set:

* every email the user sends from their own address goes out as
  "User Name (Team)" <team inbox>, with Reply-To the team inbox: chatter
  "Send message", the full composer, templates whose sender is the user
  (`{{ user.email_formatted }}`), `mail.template.send_mail` and code calling
  `message_post`. "Team" is the name of the alias's parent record (the
  helpdesk team, sales team...), else the alias local part. A Reply-To that
  is a document's own alias (a project alias, for example) is kept;
* an email whose sender is another fixed address (a template sending from
  `finance@...`) is not changed; nor are incoming emails, messages from
  OdooBot or from users without the setting;
* `{{work_email}}` in the company signature shows the team inbox instead of
  the employee's work email; the signature is regenerated when the setting
  changes;
* a reply sent to the team inbox that answers such an email (In-Reply-To /
  References) lands on the same document, even when the inbox is the alias of
  another model (core would read it as a forward and open, for example, a new
  ticket). Other recipients of the reply are routed as usual.

The team inbox must be on a domain the outgoing mail server may send from.
`mail_company_signature_helpdesk` adds the helpdesk rule (ticket emails
always go out from the ticket team's inbox).
