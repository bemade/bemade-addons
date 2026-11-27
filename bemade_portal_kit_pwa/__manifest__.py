# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
{
    'name': 'Bemade Portal Kit: Installable App',
    'version': '19.0.1.2.0',
    'category': 'Website/Portal',
    'summary': 'The portal app as an installable app: web manifest, service worker, offline page, install page.',
    'description': """
Bemade Portal Kit: Installable App
==================================

Makes the portal app of ``bemade_portal_kit`` an installable web app
(PWA): an icon on the home screen, full screen, and a data-free page when
the device is offline. Community only; depends on ``bemade_portal_kit``.

Everything follows the kit's switch (Settings › Portal App): while it is
off, the manifest, the service worker, the offline page and the icons
answer 404, the install page sends the user home, and every device that
still holds the service worker unregisters it on its next portal page (the
kill switch).

Routes
------
Stable URLs, not language-prefixed (``multilang=False``):

* ``/my/app.webmanifest``: the web manifest (``scope`` ``/``, standalone);
* ``/my/service-worker.js``: the service worker, ``Service-Worker-Allowed:
  /``, ``no-cache``;
* ``/my/app/offline``: the page shown offline. It carries no data at all:
  no layout, no user, no session information, no CSRF token;
* ``/my/app/icon/<name>``: the icons (``icon-192.png``, ``icon-512.png``,
  ``icon-maskable-512.png``, ``apple-touch-icon.png``, ``logo.png``), from
  the company's fields or the kit's neutral icons;
* ``/my/app/install`` (« More › Install the app »): the per-device steps,
  drawn on the app's layout. No install banner anywhere else.

The shell pages (``bemade_portal_kit.pk_app_layout``) link the manifest
and the iOS icon and title (template ``pk_pwa_head``, added to the
layout's head by inheritance while the switch is on).

Branding
--------
Settings › Portal App › Installable app, per company (``res.company``):
``pk_pwa_name``, ``pk_pwa_short_name``, ``pk_pwa_background_color``,
``pk_pwa_theme_color`` (``#rrggbb``) and the icons ``pk_pwa_icon_192``,
``pk_pwa_icon_512``, ``pk_pwa_icon_maskable_512``,
``pk_pwa_apple_touch_icon`` (180 px) and ``pk_pwa_logo`` (the offline
page). An empty field takes its default: the app's brand
(``portal.kit.pk_brand(app=app)``: the app's registered ``brand``, kit
1.16: one app per instance, merged over ``_pk_brand()``: the company name,
the light theme colour) and the kit's neutral icons.

``portal.kit._pk_pwa(app=None)`` returns the effective values of an app
(default: the viewer's). Version 1.1: an app sets its installable app in its
registration (``portal.kit._pk_apps()``, ``'pwa': {...}``), read by the
hooks below (extend them in an ``_inherit = 'portal.kit'``, they take the
app):

* ``_pk_pwa_start_url(app)``: ``pwa.start_url`` (default: the brand home);
* ``_pk_pwa_manifest_id(app)``: ``pwa.manifest_id`` (default: the start
  URL). Never change it on a live app: an installed app with another id is
  a second app (two apps of one database: give each its own);
* ``_pk_pwa_shortcuts(app)``: ``pwa.shortcuts``, ``[{name, url}]`` or
  ``callable(kit)`` (default: none);
* ``_pk_pwa_offline_style(pwa)``: the offline page's colours and fonts,
  ``{bg, fg, muted, accent, accent-fg, font, title-font, title-transform,
  title-spacing}`` (CSS custom properties ``--pk-offline-<key>``), with the
  app's ``pwa.offline_style`` (a dict or ``callable(kit, pwa)``) merged
  over the kit's.

Apps (version 1.1): ``/my/app.webmanifest`` (public) is the database's
default app (``portal.kit._pk_default_app()``): an app installed before
keeps its manifest URL, id and start URL. Each app also has
``/my/app/<app>.webmanifest``; a shell page links its viewer's app's
manifest (``_pk_pwa_manifest_url(app)``). The service worker and the offline
page are the default app's (one worker per site).

Service worker
--------------
``static/src/sw/pk_service_worker.js``. Navigations are network first, the
offline page when the network fails; the precached files (offline page,
its stylesheet, the logo and the 192 px icon) cache first; nothing is ever
written to a cache at run time. Cache ``pk-app-shell-<version>``: the
version combines this addon's and the kit's versions and a hash of the
effective branding, so a release or a branding edit installs a new worker,
which deletes the older ``pk-app-shell-*`` caches and the first consumer's
former ``sc-app-shell-*`` ones.

Page script ``pk_sw_register.js`` (``web.assets_frontend``): inside the
shell (``.o_pk_app[data-pk-app-shell]``) it registers the worker with scope
``/``; on any other page, it unregisters every registration of the worker
whose script answers 404 (the kill switch). Markers: ``html[data-pk-sw]``
(``registered``, ``unregistered``, ``none``) and, on the install page,
``data-pk-install``, ``data-pk-install-state`` (``installed``,
``prompt``), ``data-pk-install-steps`` and ``data-pk-install-prompt``.

Phone notifications (version 1.2)
---------------------------------
Web Push from the installed app, Community only, on Odoo's own pipeline:
its VAPID keys, ``mail.push.device``, its encryption and its cron queue
(below 5 devices Odoo sends inside the posting request). The keys are only
ever created by Odoo's own getter when missing; nothing here regenerates
them. ``portal.kit._pk_push_available()`` answers True while the switch is
on, so the kit's « Settings › Notifications » shows the phone switch of
every kind that declares ``push`` (kit 1.18) and this device's state.

* Routes (``auth='user'``, 404 while the switch is off, CSRF on POST):
  ``GET /my/app/push/key`` (the public key, a CSRF token for the worker,
  the viewer's owner tag, whether an ``endpoint`` is registered),
  ``POST /my/app/push/register`` (upsert for the caller; a previous
  endpoint is removed only if it is the caller's; an endpoint of another
  partner moves to the caller; a wrong VAPID key answers 400; the first
  registration from a « turn on » click switches the phone on for every
  phone-capable kind of the user's app), ``POST /my/app/push/unregister``
  (the caller's own endpoint only), ``POST /my/app/push/prompted`` (the
  one-time prompt was answered) and ``GET /my/app/push/badge``.
* Logout (``/web/session/logout``) removes the device the session
  registered, and the page script unregisters and unsubscribes the phone
  before following the logout link: a phone shared in a family never
  receives the previous user's messages.
* The worker: ``push`` (the notification; skipped only when a focused,
  visible window shows that conversation, never on iOS), the app badge,
  ``notificationclick`` (focus / open ``data.pk_url``) and
  ``pushsubscriptionchange`` (subscribe again and register).
* ``static/src/js/pk_push.js``: ``pkPush`` (``window.pkPush``) ``status()``
  / ``enable()`` (from a click only) / ``disable()`` / ``resync()`` /
  ``markPrompted()``; the badge from ``<meta name="pk-app-badge">`` and the
  ``pk:app-badge`` event; ``[data-pk-push-showing="<url>"]`` marks what a
  page shows.
* Share partners get Web Push only from a kind with a phone switch: Odoo's
  record-chatter push (``mail.thread``, every model but
  ``discuss.channel``) skips them. Internal users are untouched (their
  Discuss push stays on Odoo's worker, scope ``/odoo``).

Templates and nav
-----------------
``pk_app_install`` and ``pk_app_offline`` were the first consumer's
templates: their records keep their ids (install hook,
``tools/adopt.py``). Slots for a consumer's wording:
``//t[@name='pk_install_promise']``, ``//t[@name='pk_install_footnote']``
and ``//t[@name='pk_offline_message']``. The « More » entry ``install``
(every app role) and the page ``pk_app_install`` (under « More », help key
``install``) are registered by this addon.
""",
    'author': 'Bemade Inc.',
    'maintainers': ['dureposd'],
    'website': 'https://www.bemade.org',
    'license': 'LGPL-3',
    'depends': ['bemade_portal_kit', 'mail'],
    'data': [
        'views/pk_pwa_templates.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'bemade_portal_kit_pwa/static/src/js/pk_sw_register.js',
            'bemade_portal_kit_pwa/static/src/js/pk_push.js',
        ],
        'web.assets_unit_tests_setup': [
            'bemade_portal_kit_pwa/static/src/js/pk_sw_register.js',
            'bemade_portal_kit_pwa/static/src/js/pk_push.js',
        ],
        'web.assets_unit_tests': [
            'bemade_portal_kit_pwa/static/tests/*.test.js',
        ],
        'web.assets_tests': [
            'bemade_portal_kit_pwa/static/tests/tours/*.js',
        ],
    },
    'pre_init_hook': 'pre_init_hook',
    'installable': True,
    'application': False,
}
