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

Sending address
---------------

Each email a user sends has a **sending address**, computed (never stored) by
`res.users._mail_sender_info(record, email_from)`, in priority:

1. the record's own address, when the record imposes one
   (`mail.thread._mail_sender_override(user)`; `mail_company_signature_helpdesk`
   returns the ticket team's inbox);
2. the template's fixed sender (a literal address such as `purchasing@`, not a
   placeholder) when it is not one of the user's personal addresses;
3. the user's "Sending address" (user form, Settings > Users, next to the
   signature): any email alias with a domain, for example a helpdesk team's
   `sac@`;
4. the user's own address (employee work email, else user email).

Signature built for the email
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For users under the company signature policy, the signature is **built** from
the company template with `{{work_email}}` = the sending address of the
context. The stored signature is the context-free one (rule 3 or 4); when an
email goes out about a record (or with a template) whose sending address
differs, the template is rendered again for that context:

* the notification layout (chatter "Send message", replies, `message_post`),
  including the layout signing with the record's responsible;
* email templates printing a user's stored signature (`user.signature`,
  `object.user_id.signature`...): each printed copy is swapped for the
  signature built for the record and the template's sender;
* the composer: the chatter loads, with the record's data, the current
  user's signature built for that record (`mailCompanySignature`); the
  preview under « Send message » shows it and the full composer inserts it.
  What is previewed is what goes out.

Users not under the policy keep their stored (hand-written) signature, as is.

Send from the signature address (company setting)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Settings > Discuss > Emails, « Send from the signature address » (off by
default). When on, an internal user's email whose sender would be their
personal address goes out from the sending address when it is not personal:
From « Name (Team) » <inbox>, Reply-To the inbox (a record's own routing
alias in Reply-To is kept, except when the record imposes its address). A
template's fixed sender is kept; when it is a team inbox (an Odoo alias, e.g.
purchasing@), Reply-To becomes that inbox too instead of the catchall. Users
whose sending address is personal are not changed.

Replies stay on their record
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Core reads a reply addressed to an alias of another model (a helpdesk inbox)
as a forward and creates a new record through that alias. For the records of
companies with the setting on (their emails now carry a team inbox in
Reply-To), and only for them (no per-model exception), a reply that answers a message of a record and that core would turn into new
records only through such aliases lands on the record instead. A fresh email
to the inbox still creates a record. Hook: `record._mail_on_alias_reply(aliases,
message_dict)` is called after a reply lands on a record while inboxes of other
models were among its recipients (kept by this rule, or routed by core with the
inbox in Cc); a failure there never moves the reply.
