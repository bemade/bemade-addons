1. Settings > Emails > Company-standard Signature: tick the box and edit the
   template. Settings are per company.
2. Turning the policy off stops generation. Each user keeps the last generated
   signature as an editable personal signature; the original personal
   signature is stored in the user form ("Personal signature backup") and can
   be restored with "Restore personal signature".

Rollout notes:

* Review HR job titles before enabling: they are mostly single-language, and a
  bilingual title should be entered as such on the employee.
* A pronoun / addendum placeholder is intentionally not part of v1.
* The inline preview reads the signature loaded at page load; it can be stale
  until reload if the template or an employee changes mid-session. The server
  always appends the up-to-date one.
* The governing company is the user's default company, not the active one.
* Group changes made from the group form (not the user form) bypass the user
  write hook, so the personal-signature backup is not taken for such a switch.
