Stops internal followers from being flooded with chatter emails. On the models
listed in Settings > Discuss > "Email Only When Addressed", an internal user
who follows a record but is not addressed by a message (recipient, @mention,
composer Cc/Bcc) gets an in-app (inbox) notification instead of an email.
Customers, portal users and bare email recipients are not affected, and
unlisted models behave exactly as in standard Odoo.

Installing the module lists sales orders, tasks, helpdesk tickets and
accounting entries by default (only those whose app is installed). Removing a
model archives its rule, so the removal survives module upgrades.
It is independent of `mail_notification_scope`, whose strict internal-only
semantic is unchanged.
