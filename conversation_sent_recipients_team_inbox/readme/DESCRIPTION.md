Glue between `conversation_sent_recipients` and `conversation_team_inbox`.

A team mailbox drops the team's own address from the recipients before it
sends. This module records the lists that really went out on that path.
Installed automatically when both modules are present.
