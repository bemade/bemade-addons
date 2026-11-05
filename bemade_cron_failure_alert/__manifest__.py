{
    "name": "Scheduled Action Failure Alerts",
    "version": "19.0.1.2.0",
    "summary": "Warn users and a Discuss channel when a scheduled action fails "
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

it creates a *To-Do* activity for each chosen user and posts a message in
each chosen Discuss channel. Both alerts name the scheduled action, link to it and
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
* **Assign failure alerts to** - the users who receive a To-Do activity for
  the failures of EVERY scheduled action;
* **Post in channel** - the Discuss channel that receives the message.

With the option on but no user, no channel and no per-action recipient set,
failures are only logged.

Per scheduled action
--------------------

The *Alerts* group of each scheduled action (*Settings > Technical >
Scheduled Actions*) adds recipients for that action only:

* **On** (default) - the users and channel above, plus:

  * **Also alert** - more users who receive a To-Do for this action;
  * **Also post in channel** - one more channel for this action.

  These extra recipients are alerted even when the option above is off.
  A user listed both in Settings and in *Also alert* gets a single To-Do; a
  channel set in both places gets a single message.
* **Off** - nobody is alerted for this scheduled action (not even its extra
  recipients); failures are only logged.

Upgrading from 19.0.1.1.0, a scheduled action in the former *Custom* mode
becomes *On* with its user in *Also alert* and its channel kept; the single
Settings user joins the Settings user list.

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
        "views/ir_cron_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
