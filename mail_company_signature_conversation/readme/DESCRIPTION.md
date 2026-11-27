Bridge between `conversation_base` and `mail_company_signature`.

With the company setting « Send from the signature address » on, a message
written by a user with a sending address is stored as from « Name (Team) »
<team address>. A Conversations reply is not sent from that address: the
transport sends it from its own mailbox, so the stored sender was wrong, and
so were the « From: » lines of the quotes and forwards made from it.

This module leaves conversation posts out of that rewrite and records, as the
sender of a post sent over a transport, what the transport really sends from:

* a personal mailbox (IMAP, Gmail): the user's name and the mailbox login;
* a team transport: the team's login.

Nothing changes with the setting off, and any message that is not a
conversation post keeps the behaviour of `mail_company_signature`.
