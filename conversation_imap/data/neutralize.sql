-- Neutralization of generic IMAP/SMTP mailboxes: drop the stored password.
-- A neutralized database is copied around and an archived or disabled row
-- still ships its secret in every dump.
UPDATE conversation_transport
   SET password = NULL;
