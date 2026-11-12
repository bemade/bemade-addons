Show who else actually receives a message: the followers Odoo notifies.

When a message is sent from a record, Odoo also notifies every active follower subscribed
to *Discussions*, but both composers say so only with a « Followers only » placeholder
while the *To* field is empty, and say nothing once a recipient is typed. This module adds
one read-only line under the recipients of the chatter's **Send message** composer and of
the full composer:

    Also sent to followers: A, B (email) · C (Odoo inbox) · ⚠ D (no email — won't receive)

or « No followers will be notified ». It is computed from the same data the send path uses
(`mail.followers._get_recipient_data`), leaves out the sender and the partners already in
To/Cc/Bcc, and is display-only: it never changes who is notified. It is not shown for log
notes, mass mailing or batch sending.
