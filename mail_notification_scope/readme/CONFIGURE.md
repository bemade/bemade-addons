Go to Settings > Discuss > Scoped Notifications and pick the models, or tick
"Scope Notifications on All Models" (discuss channels are always excluded).
Removing a model archives its rule rather than deleting it, so a rule shipped
as `noupdate` data is not recreated on module update.

## Known limits

Paths that do not go through the notification pipeline are explicit sends and
are **not** guarded: `mail.template.send_mail`, `mail.compose.message` in
mass-mail mode, gateway bounce emails, and SMS to explicit numbers.
