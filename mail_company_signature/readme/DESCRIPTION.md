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

Write one optional line per paragraph: a paragraph whose placeholders are all
empty (for example a user without a mobile phone) is removed entirely, label
included. A paragraph mixing empty and non-empty placeholders is kept.

An administrator can exempt a user ("Manage own signature" on the user
form): that user writes their own signature again. Unticking it regenerates
the signature (the personal one is kept as backup).

The signatures are regenerated when the employee (name, phones, email, job
position or title, also on its current version), the job position (including
its French name), the template, the notice or the company changes.

The generated signature is written to `res.users.signature`, so every
existing consumer (chatter email, full composer, templates) uses it unchanged.
The inline chatter composer shows a read-only preview of the signature with a
one-click "Remove signature" toggle for the current message.
