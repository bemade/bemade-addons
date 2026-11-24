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

Signature email address
-----------------------

"Signature email address" on the user form (Settings > Users, next to the
signature) picks a team inbox: any email alias with a domain, for example the
`purchasing@` alias of a helpdesk team. Customers and suppliers then see the
team inbox in the user's signature instead of the personal address. When it is
set:

* in the signature that goes out with the user's emails, the personal address
  (user email, login when it is an address, employee work email; `mailto:`
  links and visible text, any case) is replaced by the team inbox. This works
  with hand-written signatures too, whatever the company signature policy:
  * the signature the notification layout appends (chatter "Send message",
    replies, `message_post`), including the layout signing with the record's
    responsible (`mail.mail_notification_layout_with_responsible_signature`);
  * the signature block the full composer puts in the message body;
  * signatures embedded by email templates (`user.signature`,
    `object.user_id.signature`, `object.write_uid.signature`...): each copy
    of the stored signature of a user with the setting (or of the current
    user, or of a user field of the record) is replaced at rendering time;
* only the signature changes: the same address elsewhere in the body is kept,
  and the stored signature itself is not modified;
* `{{work_email}}` in the company signature shows the team inbox instead of
  the employee's work email; the signature is regenerated when the setting
  changes;
* the sender (From) and Reply-To of the emails are NOT changed, nor is the
  routing of incoming replies. Portal users and users without the setting are
  not affected.

Known limit: the signature preview under the chatter composer shows the stored
signature (with the personal address); the email that goes out carries the
team inbox.

`mail_company_signature_helpdesk` adds the helpdesk rule (ticket emails show
the ticket team's address in the signature).
