Full-text search over the messages owned by `mail.conversation`, behind ONE
pluggable search-backend interface.

## What users get

A "Message Content" entry in the Conversations search bar. Typing words lists
the conversations having a message (subject or body text) that contains all of
them. Case and accents are ignored ("reunion" finds "réunion"); quoted
`"phrases"`, `OR` and `-exclusion` are supported. Only conversations the user
can already read are returned.

## Backend interface

`conversation.search.backend` is the only thing callers use (through
`mail.conversation.message_content` for domains and
`mail.conversation._search_by_message_content()` for ranked results). The
active backend is the `conversation_search.backend` system parameter (default
`fts`) and every operation dispatches to `_<operation>_<code>`. To plug in a
backend, extend `_get_backends()` with `super()` and implement
`_search_domain_<code>`, `_search_ranked_<code>`, `_index_messages_<code>` and
`_rebuild_index_<code>`. See the model docstring for the contract.

## The `fts` backend

A partial GIN expression index on `mail_message` (`model = 'mail.conversation'`)
over two IMMUTABLE SQL functions owned by this module: HTML is stripped to text
and accents folded without the `unaccent` extension. The `simple` text-search
configuration is used (no stop words, no stemming), so mixed French/English mail
loses no words; "pompes" does not match "pompe" (use `pompe OR pompes`). No
column is added to `mail_message`; Postgres keeps the index current in the same
statement as every write, and installing the module backfills it. Changing the
SQL functions requires bumping `FTS_VERSION`. A query made only of exclusions
(`-word`) is correct but scans the whole index.
