Lets an administrator opt chosen models into **scoped notifications**: for
those models the standard mail pipeline only ever produces in-app output
(inbox / needaction / browser notifications) for **internal users**.

- External followers, portal users and bare `outgoing_email_to` addresses
  are never notified.
- Internal users who prefer email notifications receive an inbox
  notification instead.
- Out-of-office auto-replies are not generated on scoped models.

The module is **inert by default**: nothing changes until a model is added in
Settings > Discuss, or another module ships a `mail.notification.scope`
record. `message_post`, subtypes (`mt_comment`, ...) and the notification
pipeline itself are never modified; only the computed recipients are filtered.
