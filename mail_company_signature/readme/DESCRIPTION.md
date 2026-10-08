Company-standard email signature.

Per company (Settings > Emails), an administrator can enforce one signature
template. While enforced, the signature of every internal user of that company
is generated from the template and the user's employee record, and cannot be
edited. Portal users and companies without the policy are unaffected.

Template placeholders (`{{...}}`): `name`, `job_title`, `work_phone`,
`mobile_phone`, `work_email`, `company_name`, `company_phone`,
`company_email`, `company_website`. Unknown placeholders are left as typed.

Write one optional line per paragraph: a paragraph whose placeholders are all
empty (for example a user without a mobile phone) is removed entirely, label
included. A paragraph mixing empty and non-empty placeholders is kept.

The generated signature is written to `res.users.signature`, so every
existing consumer (chatter email, full composer, templates) uses it unchanged.
The inline chatter composer shows a read-only preview of the signature with a
one-click "Remove signature" toggle for the current message.
