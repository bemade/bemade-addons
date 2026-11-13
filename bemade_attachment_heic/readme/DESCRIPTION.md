Store iPhone HEIC photos as JPEG so that Odoo and browsers can show them.

HEIC/HEIF attachments are converted to JPEG when they are uploaded (chatter, record
attachments, expenses, helpdesk/field service/quality photos, inbound email), renamed
`.jpg` and turned upright. A file that cannot be converted is kept as uploaded. Internal
users get a **Convert to JPEG** button on the HEIC attachment cards of the chatter, and an
inactive scheduled action converts the HEIC attachments stored before the module, batch by
batch, then deactivates itself.

Requires the Python package `pillow-heif`.
