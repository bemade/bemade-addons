-- Neutralization of conversation transports (base columns only).
--
-- A neutralized database is a copy that must not reach the outside world.
-- Every mailbox but the team's own is cut off here, in the data, because the
-- ``sendable`` / ``mailbox_writable`` flags are only checked by the composer
-- and the inbox viewer, not by every code path that talks to a server (an
-- inbox reply, the archive-after-filing step). The mail engine refuses to
-- open any IMAP or SMTP connection without a ``login``, before it touches the
-- network, so clearing it stops every provider, present and future, with no
-- provider-specific knowledge in this file.
--
-- Kept on purpose: names, owners, ``active``, the read flags and everything
-- filed from the mailbox. The team transport is untouched: it has no
-- credential of its own and sends through Odoo's mail server, which this
-- neutralization already points at the mail catcher. A person can connect a
-- mailbox again on purpose (typing a login, or Connect to Gmail).
UPDATE conversation_transport
   SET sendable = false,
       mailbox_writable = false,
       pushable = false,
       archive_on_capture = false,
       login = NULL
 WHERE provider IS DISTINCT FROM 'team_smtp';
