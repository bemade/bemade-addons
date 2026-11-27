#
#    Bemade Inc.
#
#    Copyright (C) October 2023 Bemade Inc. (<https://www.bemade.org>).
#    Author: Marc Durepos (Contact : marc@bemade.org)
#
#    This program is free software: you can redistribute it and/or modify it under the terms of the
#    GNU Lesser General Public License as published by the Free Software Foundation, version 3 (LGPL-3).
#    See https://www.gnu.org/licenses/lgpl-3.0.html.
#
{
    'name': 'Sports Clinic Management',
    'version': "19.0.2.0.0",
    'summary': 'Comprehensive sports medicine clinic management with portal access and activity tracking.',
    'description': """
Sports Clinic Management System

A comprehensive solution for managing sports medicine clinics, focusing on player health, injury tracking, team collaboration, and integrated activity management.

Key Features:
- User roles and access control for clinic staff, treatment professionals, and portal users
- Player management with contact information and team memberships
- Injury tracking with comprehensive documentation and workflow
- Team management with staff assignments and portal access
- Activity management with mail.activity integration
- Portal access for coaches and field therapists
- Security and privacy with layered architecture
- Data protection with anonymization and retention policies
- Full French Canadian localization support
- Integration with mail system and project tasks
- Clinic worklist for therapists and a self-service sign-in kiosk for patients

This module provides a complete sports medicine clinic management solution with robust portal access, activity tracking, and team collaboration features while maintaining strict security and data privacy controls.

Clinic sign-in kiosk (Law 25)
-----------------------------
Patients sign themselves in on an iPad at the clinic — no patient account, no
patient login. The iPad is a supervised web clip that loads ONE stable URL
(/clinic/kiosk) forever: on first load the server registers the device behind
a long-lived HttpOnly cookie, and an unbound device shows a 6-character
pairing code. The therapist types that code into the kiosk card of their
portal clinic page, which binds the device to that one clinic and its time
window (30 minutes before the start to 30 minutes after the end); the kiosk
switches to the sign-in form by itself — nobody touches the iPad. The form
asks for first name, last name and date of birth; the three are matched
server-side against the clinic's own roster only. What the kiosk does and
does not do:

- renders in French regardless of the browser language (English available as
  a per-visitor toggle), with the privacy policy an inline expandable section
  — no navigation, no off-domain link anywhere on the kiosk;
- shows no roster, no count, no autocomplete and no search; the answer to a
  sign-in is one generic welcome carrying no name;
- the date of birth is typed, never displayed back; nothing typed is echoed;
- the sign-in POST answers by redirect (PRG): reload or back can never
  resubmit; an idle kiosk returns to a clean start screen by itself;
- a successful sign-in only marks the patient Arrived on the clinic's
  worklist (source: kiosk); a sign-in that matches NO file is queued on the
  worklist as an « unregistered » row carrying only the typed first name,
  last name and date of birth — the player sees the same welcome screen —
  and the therapist resolves it in one click (link to an existing file,
  create the player from the typed data, or remove); unresolved rows are
  purged a few days after the clinic (setting, default 7 days);
- a name-only match (patient file without a date of birth) is flagged
  « to confirm » for the therapist;
- devices can be unpaired from the portal card and revoked from the backend;
  never-paired device rows are purged daily;
- pages are served with Cache-Control: no-store, no-cache, must-revalidate,
  Pragma: no-cache and X-Robots-Tag: noindex — and never touch web storage;
- server logs carry record ids only, never names or dates of birth;
- failed attempts are rate-limited per device (10 per minute, then a
  5-minute lockout) and device registration per IP.

Portal app shell (preview)
--------------------------
A new Fit Crew app shell for the portal (brand colours and type, phone
bottom tabs, laptop left rail, dark theme by default, per-user theme)
behind the system switch Settings > Portal App > Portal app (the kit's
``bemade_portal_kit.enabled``, task 5200). Switch off (the default)
leaves today's portal unchanged. Menus, sections and fields are shown from
a declarative, multi-role registry (``models/sc_app_roles.py``, on the
``portal.kit`` hooks of ``bemade_portal_kit``): a user
holds a set of roles and every entry declares the roles it includes and
excludes; security stays in the access rules. Back navigation and the
breadcrumb trail come from one parent registry (``models/sc_app_nav.py``):
back returns to the in-app page you came from (else the page's declared
parent); phones show back + context, laptops the full trail. Every history
(team announcement, training recommendation, injury notes) opens the same
way: a « History » link, a sheet fetched again on every open, one entry
format.

P1b adds the team page on the shell (dashboard, players and activities
tabs), a device draft for the team announcement (« Publier » unchanged), the
server autosave pattern (``/my/app/save``, not used live yet), and the
installable app: a ``/my/``-scoped web manifest and service worker (network
first; no team or player page is ever cached — offline shows a data-free
page), with « Plus › Installer l'application ». With the switch off, the
manifest and the service worker answer 404 and any installed worker
unregisters itself. Task 5201 (kit P6): the installable app is the kit
addon ``bemade_portal_kit_pwa`` (same URLs, scope and manifest id); the
clinic fills the company's app fields with the Fit Crew name, colours and
icons where they are empty (install and upgrade) and brings its start URL,
shortcuts, offline colours and wording.

P3 puts the therapist surfaces on the shell: the clinic list and clinic
page, whose waiting list is a LIVE component (20 s poll of
``/my/clinic/<id>/worklist/data``, status / confirm / remove / reorder
applied at once through CSRF-checked JSON routes, rolled back on failure),
events with a shared calendar component (FullCalendar from Odoo's lazy
bundle), timesheets, the notepad and the daily digests; the portal bookings
pages join through the ``bemade_sports_clinic_bookings`` glue addon. The
sign-in kiosk uses the brand tokens and self-hosted Teko / DM Sans fonts
(SIL OFL 1.1) from its own CSS-only bundle — no off-domain request.

Since the kit's P3b2 (task 5357), the shell's generic styles and the
``--pk-*`` slots live in ``bemade_portal_kit`` with neutral defaults;
``sc_tokens.scss`` is Fit Crew's brand file (palette, Teko / DM Sans,
uppercase titles, dark by default) and the clinic stylesheets keep the
clinic's own rules (``o_sc_*`` classes, ``data-sc-*`` hooks, the 1024 px
layouts).

The app dashboard (/my/home) is made of widget sections each user may show,
hide, reorder, duplicate and limit to some organisations / teams from its
« Configurer » page (task 5202: the engine, the page frame and the sheet are
bemade_portal_kit_dashboard's; ``models/sc_dashboard.py`` registers the
clinic's widgets; the layout is stored per user, versioned). A scope only ever narrows what the user may
already access. Round 1: Today, Indicators, To do (each line folds out into
its activity / injury / player cards), Recent changes, Players to watch,
Players I follow (a personal « Follow » on the player cards and page),
Announcements, Upcoming coverage (« Upcoming events » for coaches) and, for
therapists, Missing timesheets.

Instance banner: Settings > Sports Clinic Portal > Instance banner
(``bemade_sports_clinic.instance_banner``) puts a red strip with that text
(e.g. « DÉMO ») at the top of every page (login, backend, portal, app
shell) to mark a non-production instance. Empty, the default, shows
nothing; PDF reports never carry it.
    """,
    "category": "Services/Medical",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": [
        "mail",  # Required for mail.activity functionality
        "portal",
        "bemade_portal_kit",  # Task 5196: the app shell registries (roles, nav, pages)
        "bemade_portal_kit_pwa",  # Task 5201: the installable app (manifest, worker, offline / install pages)
        "bemade_portal_kit_dashboard",  # Task 5202: the configurable dashboard (engine, page frame, configure sheet)
        "contacts",
        "base_setup",  # For res.config.settings base view inheritance
        "phone_validation",  # For phone number formatting in patient contacts
        "account",  # Ensure account portal templates (e.g., portal_my_home_invoice) are available
        "sale_management",  # Sales app UI + sale.order workflow for timesheet-driven quotations
        "purchase",  # For therapist-side POs
        "hr_timesheet",  # Ensure our portal card override loads after core timesheet portal
        "data_recycle",  # Retention engine extended with the Law 25 anonymize action
    ],
    "external_dependencies": {
        "python": [
            "pytz",  # For timezone handling in injury tracking
            # Task 1536: staff phone auto-format (sports.team.staff._phone_format
            # / phone_validation) needs the optional lib; declaring it makes the
            # addon CI (manifestoo list-external-dependencies) install it.
            "phonenumbers",
        ],
    },
    "data": [
        "security/sports_clinic_groups.xml",
        "security/sports_clinic_portal_groups.xml",
        "security/ir.model.access.csv",
        "security/sports_clinic_rules.xml",
        "security/sports_clinic_portal_rules.xml",
        "security/sports_treatment_note_rules.xml",
        "security/portal_access_sweep_rules.xml",
        "security/critical_item_rules.xml",
        "security/mail_activity_portal_rules.xml",
        "security/sports_event_rules.xml",
        "security/partner_access.xml",
        "security/sports_event_timesheet_rules.xml",
        "security/team_digest_rules.xml",
        "security/sports_quick_note_rules.xml",
        "security/sports_clinic_attendance_rules.xml",
        "security/training_history_rules.xml",
        # Task 1401: personal /my/teams order, own-rows-only rule.
        "security/sports_team_user_rank_rules.xml",
        "data/sports_clinic_data.xml",
        "data/material_report_data.xml",
        "data/admin_access_data.xml",
        # "data/project_portal_demo_data.xml",  # Temporarily disabled for clean upgrade
        "data/cron_actions.xml",
        "data/sc_activity_todo_data.xml",
        "data/data_recycle_model.xml",
        # Must precede sports_team_views.xml: its header button resolves
        # %(action_team_player_removal)d at parse time.
        "views/team_player_removal_wizard_views.xml",
        "views/sports_team_views.xml",
        "views/sports_patient_injury_views.xml",
        "views/sports_clinic_menus.xml",
        "data/sc_guide_video_assets.xml",
        "data/sc_knowledge_public_view.xml",
        # Task 5200 (kit P5): the in-app help moved to the kit
        # (portal.kit.help); the clinic's back-end menu entry.
        "views/sc_app_help_views.xml",
        # Task 1399: attendance report (pivot/graph/list) + the Reports menu.
        # After the menus (parent = sports_clinic_root), before the event views
        # (their smart-button action points at these views' model).
        "views/sports_clinic_attendance_views.xml",
        "views/team_digest_views.xml",
        "views/sports_patient_views.xml",
        # Task 1414: the portal patient combo snippet (typeahead over a real
        # <select>, « Last, First »). Load before every template that t-calls it.
        "views/portal_widgets_templates.xml",
        "views/sports_clinic_portal_views.xml",
        "views/team_digest_portal_templates.xml",
        "views/event_invoicing_wizard_views.xml",
        "views/event_batch_invoicing_wizard_views.xml",
        "views/event_vendor_po_wizard_views.xml",
        "views/purchase_order_views.xml",
        "views/event_recurrence_wizard_views.xml",
        "views/event_cancel_wizard_views.xml",
        "views/res_config_settings_views.xml",
        "views/sports_event_views.xml",
        "views/treatment_note_views.xml",
        "views/sports_quick_note_views.xml",
        # Task 1397/1433: the public clinic sign-in kiosk (stable
        # /clinic/kiosk dispatcher, device bound by pairing code).
        "views/clinic_kiosk_templates.xml",
        # Task 1433: backend admin for the kiosk devices (system only).
        "views/sports_clinic_kiosk_device_views.xml",
        # Task 1415: organization staff (line views, promotion wizard). Must
        # precede res_partner_views.xml: the org form's « Promote » button
        # resolves %(action_team_org_staff_promote)d at parse time.
        "views/sports_organization_staff_views.xml",
        # Task 1416: temporary (dated) staff access grants — list / form /
        # action + Admin menu; the team form's smart button and the org form's
        # list use them.
        "views/sports_staff_grant_views.xml",
        "views/res_partner_views.xml",
        "views/team_role_mass_assign_wizard_views.xml",
        "views/patient_merge_wizard_views.xml",
        "views/patient_duplicate_views.xml",
        "views/res_users_views.xml",
        # Task 1538: the portal app shell (behind the app_shell_enabled
        # switch) — components, layout, then the pages that t-call them.
        "views/sc_components.xml",
        "views/sc_app_layout.xml",
        # Task 1541 (P4): « Pas d'accès » for a user without a clinic app role.
        "views/sc_no_access.xml",
        "views/instance_banner.xml",
        "views/sc_app_player_add.xml",
        "views/sc_app_pages.xml",
        # Task 1624: the dashboard (/my/home) widgets (task 5202: the frame
        # and « Configurer » are bemade_portal_kit_dashboard's).
        "views/sc_app_dashboard.xml",
        # Task 1542: team page (task 5201: the install and offline pages are
        # bemade_portal_kit_pwa's; sc_app_pwa.xml words them for Fit Crew).
        "views/sc_app_team.xml",
        "views/sc_app_pwa.xml",
        # Task 1539: P2 — players, injuries, notes, documents, activities.
        "views/sc_app_activities.xml",
        "views/sc_app_players.xml",
        "views/sc_app_injury.xml",
        # Task 1540: P3 — clinic (list, page, live waiting list).
        "views/sc_app_clinic.xml",
        "views/sc_app_events.xml",
        "views/sc_app_tools.xml",
    ],
    "demo": [
        "data/demo/sports_clinic_demo_data.xml",
        "data/demo/sports_clinic_demo_extras.xml",
        "data/demo/sports_clinic_demo_products.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": True,
    'post_init_hook': 'post_init_hook',
    "assets": {
        "web.assets_backend": [
            # Task 1272: single-column full-width team-dashboard digest kanban.
            "bemade_sports_clinic/static/src/scss/dashboard_kanban.scss",
            # Task 1272 (round 3): « voir plus »/« voir moins » de-dup — shared
            # with the portal so both surfaces toggle identically.
            "bemade_sports_clinic/static/src/scss/dashboard_digest.scss",
        ],
        "web.assets_frontend": [
            # Ensure legacy jQuery helpers exist where some website widgets expect them
            "bemade_sports_clinic/static/src/js/jquery_scrolling_polyfill.js",
            # Defensive patch for website TOC snippet to avoid null textContent errors
            "bemade_sports_clinic/static/src/js/website_toc_safety_patch.js",
            "bemade_sports_clinic/static/src/scss/portal_badges.scss",
            # Task 1272 (round 3): same digest « voir plus » de-dup on the portal.
            "bemade_sports_clinic/static/src/scss/dashboard_digest.scss",
            # Task 1385: the player card's <details> expandable (the digest
            # snapshot card) and the static injury detail block.
            "bemade_sports_clinic/static/src/scss/portal_card.scss",
            # Task 1414: portal patient combo — typeahead over the rendered
            # <select> options (clinic add-patient, quick-note pickers).
            # Progressive enhancement — the plain select posts without it.
            "bemade_sports_clinic/static/src/scss/portal_widgets.scss",
            "bemade_sports_clinic/static/src/js/portal_patient_combo.js",
            # Task 1538: portal app shell (since task 5357 the brand file +
            # the clinic's own rules; the generic ones are the kit's), scoped
            # under .o_pk_app — inert outside the shell; task 5345: the theme
            # preference script is the kit's, pk_theme_pref.js). Not
            # duplicated in the lazy list.
            "bemade_sports_clinic/static/src/scss/sc_tokens.scss",
            "bemade_sports_clinic/static/src/scss/sc_components.scss",
            # Task 1542: P1b — page styles, the one fetch helper, the device
            # draft store, page behaviours (tabs / sheets / lazy rows /
            # toast), the service worker registration + kill switch, and the
            # addon's first OWL public component (same bundle as core's
            # portal.signature_form). assets_frontend ONLY: the lazy bundle
            # includes this one, listing them there too would bind twice.
            "bemade_sports_clinic/static/src/scss/sc_pages.scss",
            # Task 1539: P2 page / component styles.
            "bemade_sports_clinic/static/src/scss/sc_p2.scss",
            # Task 5197 (kit P2): the shell's 13 generic scripts moved to
            # bemade_portal_kit (pk_*.js, bundled by the kit, a dependency);
            # task 5198 (P3a) removed their one-release aliases.
            "bemade_sports_clinic/static/src/js/sc_app_ui.js",
            # Task 1660: guide videos on the public Knowledge article pages.
            "bemade_sports_clinic/static/src/js/sc_guide_video.js",
            # Task 1652: the red card pills open the medical popups.
            "bemade_sports_clinic/static/src/js/sc_med_card_pills.js",
            # Task 1677: the allergy / condition lists and the EpiPen card
            # of the medical popups.
            "bemade_sports_clinic/static/src/js/sc_medical_lists.js",
            # Task 1655: create a player inline (existence check as you type).
            # Task 5370 (kit P4b): the form guard moved to the kit
            # (pk_form_guard.js); sc_guard_rules.js is the clinic's own
            # « assign » rule of the kit's guard.
            "bemade_sports_clinic/static/src/js/sc_guard_rules.js",
            "bemade_sports_clinic/static/src/js/sc_player_add.js",
            # Task 1603: follow-up proposals (the sheet after a save).
            "bemade_sports_clinic/static/src/js/sc_proposal.js",
            # Task 1604: quick « Vérifier » / « Résoudre » of an injury.
            "bemade_sports_clinic/static/src/js/sc_injury_quick.js",
            "bemade_sports_clinic/static/src/js/sc_injury_card.js",
            # Task 1624 review round 1: « Suivre » a player (fetch toggle).
            "bemade_sports_clinic/static/src/js/sc_follow.js",
            # Task 1624 review round 2: the quick « Retour prévu » (task 5202:
            # the configure sheet and the scroll anchoring are
            # bemade_portal_kit_dashboard's).
            "bemade_sports_clinic/static/src/js/sc_dashboard_live.js",
            # Task 1539: the shell's activity sheets (replaces, in the shell
            # only, the legacy activity partials' inline scripts).
            "bemade_sports_clinic/static/src/js/sc_activities.js",
            # Task 1540: P3 styles, the live clinic waiting list.
            "bemade_sports_clinic/static/src/scss/sc_p3.scss",
            "bemade_sports_clinic/static/src/scss/sc_dashboard.scss",
            "bemade_sports_clinic/static/src/js/sc_clinic_worklist.js",
            "bemade_sports_clinic/static/src/js/sc_clinic_worklist.xml",
            # Task 1540: the event form behaviours (task 5200: the calendar
            # is the kit's pk_calendar; task 1541: its one-release alias of
            # the old OWL key is gone).
            "bemade_sports_clinic/static/src/js/sc_events.js",
        ],
        # Task 1540: the sign-in kiosk's OWN stylesheet bundle, included
        # CSS-ONLY by clinic_kiosk_layout (t-js="false"). Not
        # web.assets_frontend: with `website` installed that bundle may
        # @import the website's Google Fonts — the kiosk must make NO
        # off-domain request (its iPad is URL-filtered). Bootstrap + Font
        # Awesome (same origin) + the brand tokens / self-hosted fonts.
        "bemade_sports_clinic.assets_kiosk": [
            ("include", "web._assets_helpers"),
            ("include", "web._assets_frontend_helpers"),
            "web/static/src/scss/pre_variables.scss",
            "web/static/lib/bootstrap/scss/_variables.scss",
            "web/static/lib/bootstrap/scss/_variables-dark.scss",
            "web/static/lib/bootstrap/scss/_maps.scss",
            ("include", "web._assets_bootstrap_frontend"),
            "web/static/src/libs/fontawesome/css/font-awesome.css",
            # Task 5357 (kit P3b2): the kit's variables and slot mixins
            # (pk-scale-tokens) before the brand file.
            "bemade_portal_kit/static/src/scss/pk_variables.scss",
            "bemade_portal_kit/static/src/scss/pk_tokens.scss",
            "bemade_sports_clinic/static/src/scss/sc_tokens.scss",
            "bemade_sports_clinic/static/src/scss/sc_kiosk.scss",
        ],
        # Task 1542: the addon's first browser tours.
        "web.assets_tests": [
            "bemade_sports_clinic/static/tests/tours/**/*",
        ],
    },
}
