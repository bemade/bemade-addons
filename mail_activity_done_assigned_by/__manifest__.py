{
    "name": "Activity Done: Assigned By",
    "version": "19.0.1.0.0",
    "category": "Productivity/Discuss",
    "summary": "Show who assigned an activity, when, and its deadline in the "
    "chatter message posted when it is marked as done.",
    "description": """
Activity Done: Assigned By
==========================

When an activity is marked as done, Odoo posts a "<type> done" message in the
chatter of the document. That message says who closed the activity (its author)
and, when someone else closed it, who it was originally assigned to. It never
says who **created** the activity, although the archived activity keeps that
information.

This module adds one line under the title of that message:

* ``Assigned by <creator> on <creation date> · due <deadline>`` when the
  activity was created by someone other than the user marking it as done;
* ``Created automatically on <creation date> · due <deadline>`` when the
  activity was created by the superuser (OdooBot: crons, server actions run as
  superuser...). The superuser's name is never shown.

Activities a user scheduled for themselves and closes themselves keep the core
message unchanged. The core "(originally assigned to ...)" mention, the original
note, the feedback and the attachments are untouched.

Notes
-----

* Like every chatter message, the "done" message is rendered once, at
  done-time, in the language of the user marking the activity as done; dates
  use that user's timezone. Messages posted before installation are not
  rewritten.
* **Forced language.** A company can set *Language of activity completion
  messages* (Settings > Discuss > Activity completion messages). When set, the
  whole "done" message — core title, this line and its dates — is written in
  that language whatever the closer's language (e.g. always French, for a
  company bound by Quebec's Charter of the French Language). Empty (default):
  the closer's language.
* An activity created by an automation that runs as the triggering user (e.g. a
  leave request creating its approval activity) is shown as "Assigned by
  <that user>", because that user is its creator.
* QWeb inheritance of ``mail.message_activity_done`` for the line; the forced
  language is a context switch around ``mail.activity._action_done``.
""",
    "author": "Bemade Inc.",
    "maintainers": ["dureposd"],
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": ["mail"],
    "data": [
        "data/mail_templates_chatter.xml",
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
