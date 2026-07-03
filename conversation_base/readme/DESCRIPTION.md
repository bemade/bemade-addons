Introduces `mail.conversation` as a first-class triage unit, independent of
any single business record (sale order, ticket, invoice, ...).

## Why

Odoo's chatter ties a message thread to exactly one `res_model`/`res_id`.
Real-world email triage does not: a single conversation can be about several
records, and a single record can spawn several distinct conversations over
time. This module reifies the conversation itself as its own model, with:

- `mail.conversation` -- the conversation (state, assignee, team, tags,
  primary transport), inheriting the standard chatter (`mail.thread`),
  activities (`mail.activity.mixin`) and an inbound email alias
  (`mail.alias.mixin`).
- `mail.conversation.link` -- a reified generic link from a conversation to
  any number of business records (`res_model`/`res_id`), so a
  conversation<->record relationship is many-to-many instead of the native
  one-to-one chatter link.
- `mail.conversation.participant` -- who is on a conversation (partner or
  bare email address), distinct from `mail.followers`: adding a participant
  never subscribes anyone.
- `mail.conversation.member` -- per-user triage state (handled/unread/
  snoozed) on a conversation, independent of the conversation's own `state`.
- `mail.conversation.team` -- a dedicated team model for conversations,
  independent of CRM/Helpdesk/Discuss channel teams.
- `mail.conversation.tag` -- simple tags for conversations.
- `conversation.transport` -- a minimal stub comodel for the outbound/inbound
  channel (email, SMS, ...) a conversation or message travels over; later
  epics extend it with provider-specific behavior.
- `mail.message` is extended with `transport_id` and `external_id` so
  individual messages can be told apart from internal notes and correlated
  back to the native message id of the originating transport.

This module ships the skeleton only: no transports, no notify-safety
overrides, no triage UI beyond a basic list/form/kanban to exercise the
model. Those are delivered by later epics.
