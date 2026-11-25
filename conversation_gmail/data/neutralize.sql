-- Neutralization of Gmail mailboxes: drop every stored Google credential, the
-- OAuth tokens (columns of google.gmail.mixin on conversation_transport) and
-- the account's own client id and secret.
--
-- The instance-wide Google client (the ``google_gmail_client_id`` and
-- ``google_gmail_client_secret`` system parameters, and the tokens of
-- ir_mail_server / fetchmail_server rows) belongs to Odoo core and is left to
-- its neutralization. A mailbox can be connected again afterwards.
UPDATE conversation_transport
   SET google_gmail_refresh_token = NULL,
       google_gmail_access_token = NULL,
       google_gmail_access_token_expiration = 0,
       client_id = NULL,
       client_secret = NULL;
