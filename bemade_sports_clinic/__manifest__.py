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
    'version': "19.0.1.141.0",
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
behind the system switch Settings > Sports Clinic Portal > New Portal App
(``bemade_sports_clinic.app_shell_enabled``). Switch off (the default)
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
unregisters itself.

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
« Configurer » page (one registry: ``models/sc_dashboard.py``; the layout is
stored per user, versioned). A scope only ever narrows what the user may
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
        "views/sc_help_article_views.xml",
        "data/sc_guide_video_assets.xml",
        "data/sc_knowledge_public_view.xml",
        # Task 1399: attendance report (pivot/graph/list) + the Reports menu.
        # After the menus (parent = sports_clinic_root), before the event views
        # (their smart-button action points at these views' model).
        "views/sports_clinic_attendance_views.xml",
        "views/team_digest_views.xml",
        "views/sports_patient_views.xml",
        # Task 1384: shared "Effacer"/Clear macro for long-text portal fields.
        # Load before the portal templates that t-call it.
        "views/portal_field_clear_templates.xml",
        # Task 1414: the portal patient combo snippet (typeahead over a real
        # <select>, « Last, First »). Load before every template that t-calls it.
        "views/portal_widgets_templates.xml",
        "views/sports_clinic_portal_views.xml",
        "views/team_digest_portal_templates.xml",
        "views/sports_patient_injury_portal.xml",
        "views/player_management_portal_templates.xml",
        "views/injury_management_portal_templates.xml",
        "views/injury_note_history_portal_templates.xml",
        "views/task_management_portal_templates.xml",
        "views/events_portal_templates.xml",
        "views/event_invoicing_wizard_views.xml",
        "views/event_batch_invoicing_wizard_views.xml",
        "views/event_vendor_po_wizard_views.xml",
        "views/purchase_order_views.xml",
        "views/event_recurrence_wizard_views.xml",
        "views/event_cancel_wizard_views.xml",
        "views/res_config_settings_views.xml",
        "views/sports_event_views.xml",
        "views/portal_activity_detail_template.xml",
        "views/portal_event_detail_template.xml",
        "views/portal_event_edit_template.xml",
        "views/portal_event_create_template.xml",
        "views/portal_timesheets_templates.xml",
        "views/treatment_note_views.xml",
        "views/sports_quick_note_views.xml",
        "views/quick_note_portal_templates.xml",
        # Task 1398: the TP clinic worklist (/my/clinics, /my/clinic/<id>).
        "views/clinic_portal_templates.xml",
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
        "views/instance_banner.xml",
        "views/sc_app_search.xml",
        "views/sc_app_player_add.xml",
        "views/sc_app_pages.xml",
        # Task 1624: the dashboard (/my/home) widgets + « Configurer ».
        "views/sc_app_dashboard.xml",
        "views/sc_app_account.xml",
        # Task 1542: team page, install page, offline page.
        "views/sc_app_team.xml",
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
            # Task 1385: homogenized portal card expandable styling + the
            # lazy-load toggle listener for the recent-changes feed.
            "bemade_sports_clinic/static/src/scss/portal_card.scss",
            "bemade_sports_clinic/static/src/js/portal_card_recent_changes.js",
            # Task 1389: lazy-loader for the team-dashboard digest-history modal.
            "bemade_sports_clinic/static/src/js/portal_digest_history.js",
            # Task 1384: one-tap "Effacer"/Clear for long-text portal fields.
            "bemade_sports_clinic/static/src/js/portal_field_clear.js",
            # Task 1398: desktop drag-reorder for the clinic worklist (plus its
            # small drag affordance styling). Progressive enhancement only — the
            # up/down buttons work without it. Task 1401: the same script/styles
            # drive the /my/teams personal order (data-reorder-* opt-in).
            "bemade_sports_clinic/static/src/scss/portal_clinic.scss",
            "bemade_sports_clinic/static/src/js/portal_clinic_reorder.js",
            # Task 1397: worklist auto-refresh (20 s poll of the fragment route
            # while the tab is visible) + the kiosk-link Copy button. Both are
            # progressive enhancement — reload / select-the-text work without.
            "bemade_sports_clinic/static/src/js/portal_clinic_worklist_refresh.js",
            # Task 1411: snap the dossier's match / practice selects to a valid
            # pair. Progressive enhancement — the server validates regardless.
            "bemade_sports_clinic/static/src/js/portal_clinic_quick_status.js",
            # Task 1412: the dossier's injury modal (quick-add / edit form
            # fragments fetched into #clinicInjuryModal). Progressive
            # enhancement — the same links open the full pages without it.
            "bemade_sports_clinic/static/src/js/portal_clinic_injury_modal.js",
            # Task 1413: « Cancel » of the inline treatment-note edit form
            # (clinic notes table + player notes tab). Progressive enhancement
            # — the <details> summary opens / closes the form without it.
            "bemade_sports_clinic/static/src/js/portal_treatment_note_edit.js",
            # Task 1414: portal patient combo — typeahead over the rendered
            # <select> options (clinic add-patient, quick-note pickers).
            # Progressive enhancement — the plain select posts without it.
            "bemade_sports_clinic/static/src/scss/portal_widgets.scss",
            "bemade_sports_clinic/static/src/js/portal_patient_combo.js",
            # Task 1538: portal app shell (since task 5357 the brand file +
            # the clinic's own rules; the generic ones are the kit's), scoped
            # under .o_pk_app — inert outside the shell; the JS only acts on
            # data-sc-pref forms inside it). Not duplicated in the lazy list.
            "bemade_sports_clinic/static/src/scss/sc_tokens.scss",
            "bemade_sports_clinic/static/src/scss/sc_components.scss",
            "bemade_sports_clinic/static/src/js/sc_app_shell.js",
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
            "bemade_sports_clinic/static/src/js/sc_help.js",
            # Task 1660: guide videos on the public Knowledge article pages.
            "bemade_sports_clinic/static/src/js/sc_guide_video.js",
            # Task 1650: the header search (magnifier, « / », Ctrl/⌘-K).
            "bemade_sports_clinic/static/src/js/sc_search.js",
            # Task 1648: the type-to-filter picker of the link fields.
            "bemade_sports_clinic/static/src/js/sc_picker.js",
            # Task 1652: the red card pills open the medical popups.
            "bemade_sports_clinic/static/src/js/sc_med_card_pills.js",
            # Task 1677: the allergy / condition lists and the EpiPen card
            # of the medical popups.
            "bemade_sports_clinic/static/src/js/sc_medical_lists.js",
            # Task 1655: create a player inline (existence check as you type).
            # Task 5370 (kit P4b): the form guard moved to the kit
            # (pk_form_guard.js); sc_form_guard.js is the one-release alias of
            # the old module path (re-exports only), sc_guard_rules.js the
            # clinic's own « assign » rule of the kit's guard.
            "bemade_sports_clinic/static/src/js/sc_form_guard.js",
            "bemade_sports_clinic/static/src/js/sc_guard_rules.js",
            "bemade_sports_clinic/static/src/js/sc_player_add.js",
            # Task 1603: follow-up proposals (the sheet after a save).
            "bemade_sports_clinic/static/src/js/sc_proposal.js",
            # Task 1604: quick « Vérifier » / « Résoudre » of an injury.
            "bemade_sports_clinic/static/src/js/sc_injury_quick.js",
            # Task 1627: status pill dropdowns (Match / Practice) — task 5370
            # (kit P4b): moved to the kit (pk_status_pills.js); one-release
            # alias of the old module path.
            "bemade_sports_clinic/static/src/js/sc_status_pills.js",
            "bemade_sports_clinic/static/src/js/sc_injury_card.js",
            "bemade_sports_clinic/static/src/js/sc_account.js",
            "bemade_sports_clinic/static/src/js/sc_sw_register.js",
            # Task 1624: « Configurer » the dashboard (saves as you go).
            "bemade_sports_clinic/static/src/js/sc_dashboard_config.js",
            # Task 1624 review round 1: « Suivre » a player (fetch toggle).
            "bemade_sports_clinic/static/src/js/sc_follow.js",
            # Task 1624 review round 2: the dashboard's two fixed columns,
            # scroll anchoring of its fold-outs, the quick « Retour prévu ».
            "bemade_sports_clinic/static/src/js/sc_dashboard_live.js",
            "bemade_sports_clinic/static/src/js/sc_autosave_field.js",
            "bemade_sports_clinic/static/src/js/sc_autosave_field.xml",
            # Task 1736 r1: an activity card's edit fields, mounted on its
            # first pencil tap — task 5370 (kit P4b): moved to the kit
            # (pk_lazy_edit.js); one-release alias of the old module path.
            "bemade_sports_clinic/static/src/js/sc_lazy_edit.js",
            # Task 1539: the shell's activity sheets (replaces, in the shell
            # only, the legacy activity partials' inline scripts).
            "bemade_sports_clinic/static/src/js/sc_activities.js",
            # Task 1540: P3 styles, the live clinic waiting list.
            "bemade_sports_clinic/static/src/scss/sc_p3.scss",
            "bemade_sports_clinic/static/src/scss/sc_dashboard.scss",
            # Task 1620: « Mon compte » / « Sécurité » in the shell.
            "bemade_sports_clinic/static/src/scss/sc_account.scss",
            "bemade_sports_clinic/static/src/js/sc_clinic_worklist.js",
            "bemade_sports_clinic/static/src/js/sc_clinic_worklist.xml",
            # Task 1540: the shared calendar (FullCalendar lazy-loaded from
            # web.fullcalendar_lib) and the event form behaviours.
            "bemade_sports_clinic/static/src/js/sc_calendar.js",
            "bemade_sports_clinic/static/src/js/sc_calendar.xml",
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
        # Also load in lazy bundle since many website widgets initialize lazily
        "web.assets_frontend_lazy": [
            "bemade_sports_clinic/static/src/js/jquery_scrolling_polyfill.js",
            # Ensure patch is also present in lazy assets where snippet may initialize
            "bemade_sports_clinic/static/src/js/website_toc_safety_patch.js",
            # Task 1385: the card lazy-loader must also be present where portal
            # pages initialize via the lazy bundle.
            "bemade_sports_clinic/static/src/js/portal_card_recent_changes.js",
            # Task 1389: digest-history modal loader also present in lazy bundle.
            "bemade_sports_clinic/static/src/js/portal_digest_history.js",
            # Task 1384: clear control also present in lazy bundle.
            "bemade_sports_clinic/static/src/js/portal_field_clear.js",
            # Task 1398: clinic worklist drag also present in lazy bundle.
            "bemade_sports_clinic/static/src/scss/portal_clinic.scss",
            "bemade_sports_clinic/static/src/js/portal_clinic_reorder.js",
            # Task 1397: worklist auto-refresh also present in lazy bundle.
            "bemade_sports_clinic/static/src/js/portal_clinic_worklist_refresh.js",
            # Task 1411: quick status snap also present in lazy bundle.
            "bemade_sports_clinic/static/src/js/portal_clinic_quick_status.js",
            # Task 1412: injury modal loader also present in lazy bundle.
            "bemade_sports_clinic/static/src/js/portal_clinic_injury_modal.js",
            # Task 1413: note edit cancel also present in lazy bundle.
            "bemade_sports_clinic/static/src/js/portal_treatment_note_edit.js",
            # Task 1414: patient combo also present in lazy bundle.
            "bemade_sports_clinic/static/src/scss/portal_widgets.scss",
            "bemade_sports_clinic/static/src/js/portal_patient_combo.js",
        ],
    },
}
