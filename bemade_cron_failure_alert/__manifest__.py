{
    "name": "Scheduled Action Failure Alerts",
    "version": "19.0.1.0.0",
    "summary": "Warn a user and a Discuss channel when a scheduled action fails "
    "or is switched off by Odoo.",
    "description": """
Scheduled Action Failure Alerts
===============================

Odoo 19 counts the consecutive failures of each scheduled action (``ir.cron``)
and silently switches the action off once it has failed at least five times
over more than seven days. The only trace is a warning in the server log, so a
nightly job can stop for weeks before anybody notices.

This module turns that bookkeeping into alerts people actually see:

* on the **first failure** of a streak, and
* when Odoo **switches the action off** after repeated failures,

it creates a *To-Do* activity for a chosen user and posts a message in a
chosen Discuss channel. Both alerts name the scheduled action, link to it and
include the end of the error traceback when one was raised (a run that timed
out has no traceback; the alert then points to the server log time).

There is exactly one alert per failure streak plus one on deactivation, never
one per run. A successful run ends the streak, so the next failure alerts
again. Each scheduled action keeps a single open To-Do per user: while it is
not marked done, a new alert is added on top of its note (and its deadline
moves to today) instead of creating another one.

Configuration
-------------

*Settings > General Settings > Discuss > Scheduled action failures*:

* **Alert on scheduled action failures** - turns the alerts on;
* **Assign failure alerts to** - the user who receives the To-Do activity;
* **Post in channel** - the Discuss channel that receives the message.

With the option on but neither a user nor a channel set, failures are only
logged.

Safety
------

The alert is written in its own database transaction, and any error while
writing it is logged and swallowed: an alert can never make the scheduled
action's own bookkeeping (failure counter, next call, deactivation) fail.
""",
    "category": "Hidden/Tools",
    "author": "Bemade Inc.",
    "maintainer": "Denis Durepos <denis@bemade.org>",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": ["mail"],
    "data": [
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
