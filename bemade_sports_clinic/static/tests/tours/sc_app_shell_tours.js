/*
 * Task 1542 (epic #1535) — browser tours of the portal app shell (the
 * addon's first). Run by tests/test_app_shell_tours_1542.py through
 * HttpCase.start_tour, which opens the start URL; language-independent
 * triggers only (data attributes).
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function draftKeys() {
    const keys = [];
    for (let i = 0; i < window.localStorage.length; i++) {
        const key = window.localStorage.key(i);
        if (key && key.startsWith("pk_draft:")) {
            keys.push(key);
        }
    }
    return keys;
}

// ---------------------------------------------------------------- nav
tours.add("sc_1542_nav_phone", {
    steps: () => [
        {
            content: "Phone: bottom tabs shown, « Équipes » active",
            trigger: '.o_pk_tabs a[data-pk-nav-key="teams"][aria-current="page"]',
        },
        {
            content: "Phone: no left rail",
            trigger: ".o_pk_rail:not(:visible)",
        },
        {
            content: "Open « Plus » from the tabs",
            trigger: '.o_pk_tabs a[data-pk-nav-key="more"]',
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "« Plus » is the active tab and lists « Installer l'application »",
            trigger: '.o_pk_tabs a[data-pk-nav-key="more"][aria-current="page"]',
        },
        {
            trigger: 'main a[data-pk-nav-key="install"]',
        },
    ],
});

tours.add("sc_1542_nav_laptop", {
    steps: () => [
        {
            content: "Laptop: left rail shown, « Équipes » active",
            trigger: '.o_pk_rail_nav a[data-pk-nav-key="teams"][aria-current="page"]',
        },
        {
            content: "Laptop: no bottom tabs",
            trigger: ".o_pk_tabs:not(:visible)",
        },
        {
            content: "Open « Plus » from the rail",
            trigger: '.o_pk_rail_nav a[data-pk-nav-key="more"]',
            run: "click",
            expectUnloadPage: true,
        },
        {
            trigger: '.o_pk_rail_nav a[data-pk-nav-key="more"][aria-current="page"]',
        },
    ],
});

// ------------------------------------------------- theme (+ laptop crumbs)
tours.add("sc_1542_prefs", {
    steps: () => [
        {
            content: "Dark by default; mark the page to detect a reload",
            trigger: '.o_pk_app[data-pk-theme="dark"]',
            run() {
                window.__sc1542NoReload = true;
            },
        },
        {
            content: "Toggle the theme from the app bar",
            trigger: ".o_pk_theme_toggle button",
            run: "click",
        },
        {
            content: "Light theme applied IN PLACE (no reload)",
            trigger: '.o_pk_app[data-pk-theme="light"]',
            run() {
                assert(window.__sc1542NoReload, "the theme toggle reloaded the page");
                assert(document.body.classList.contains("o_pk_app_body_light"), "body class");
            },
        },
        {
            content: "Go to « Paramètres » (task 1606: out of « Plus »)",
            trigger: '.o_pk_app[data-pk-theme="light"]',
            run() {
                window.location.assign("/my/app/settings");
            },
            expectUnloadPage: true,
        },
        {
            content: "Light theme persisted; no navigation setting (task 1579)",
            trigger: '.o_pk_app[data-pk-theme="light"] #pk_appearance',
            run() {
                assert(!document.querySelector("#sc_navigation"), "« Navigation » setting still there");
                window.location.assign("/my/teams");
            },
            expectUnloadPage: true,
        },
        {
            content: "Open a team (a sub-page of « Équipes »)",
            trigger: "main a[data-sc-team-id]",
            run: "click",
            expectUnloadPage: true,
        },
        {
            // Task 1618 (owner review 2026-10-18): the chevron always shows
            // next to the trail on a laptop sub-page.
            content: "Laptop: the crumb trail shows, and the back chevron too",
            trigger: 'nav.o_pk_crumbs a[href$="/my/teams"]',
            run() {
                const back = document.querySelector(".o_pk_back");
                assert(back && back.offsetParent, "back chevron hidden on a laptop");
            },
        },
    ],
});

// ---------------------------------------------------------- team tabs
tours.add("sc_1542_team_tabs", {
    steps: () => [
        {
            content: "Dashboard panel shown first; mark the page",
            trigger: 'section[data-pk-tab-panel="dashboard"]',
            run() {
                window.__sc1542NoReload = true;
            },
        },
        {
            content: "Open the players tab",
            trigger: '[data-pk-tabs] a[data-pk-tab="players"]',
            run: "click",
        },
        {
            content: "Players panel shown in place, ?tab= kept in the address bar",
            trigger: 'section[data-pk-tab-panel="players"] [data-pk-section="team.roster"]',
            run() {
                assert(window.__sc1542NoReload, "tab switch reloaded the page");
                assert(window.location.search.includes("tab=players"), "tab not in URL");
                assert(
                    document.querySelector('section[data-pk-tab-panel="dashboard"]').hidden,
                    "dashboard still visible"
                );
            },
        },
        {
            content: "Open the activities tab",
            trigger: '[data-pk-tabs] a[data-pk-tab="activities"]',
            run: "click",
        },
        {
            trigger: 'section[data-pk-tab-panel="activities"] [data-pk-section="activities.list"]',
        },
        {
            content: "Back to the dashboard",
            trigger: '[data-pk-tabs] a[data-pk-tab="dashboard"]',
            run: "click",
        },
        {
            // Task 1579: « History » is a link to the digest list (no sheet).
            content: "« History » goes to the digest list page",
            trigger: 'a[data-sc-action="team.digest_history"][href$="/digest-history"]',
            run() {
                assert(!document.querySelector("#sc_digest_history_sheet"), "digest sheet still there");
            },
        },
    ],
});

// ------------------------------------------------ announcement draft (AC3)
const DRAFT_TEXT = "Tour 1542 synthetic draft";

tours.add("sc_1542_announcement_draft", {
    steps: () => [
        {
            content: "Open the compose form (the announcement card's pencil)",
            trigger: '[data-pk-edit-card="announcement"] button[data-pk-edit-toggle]',
            run(helpers) {
                window.sessionStorage.setItem("sc1542TeamUrl", window.location.href);
                return helpers.click();
            },
        },
        {
            content: "Type the announcement",
            trigger: "#sc_team_announcement",
            run: `edit ${DRAFT_TEXT}`,
        },
        {
            content: "Draft kept on the device",
            trigger: '.o_pk_autosave[data-pk-autosave-state="draft"]',
            run() {
                assert(draftKeys().length === 1, "expected one device draft");
            },
        },
        {
            content: "Leave the page",
            trigger: '.o_pk_autosave[data-pk-autosave-state="draft"]',
            run() {
                window.location.assign("/my/home");
            },
            expectUnloadPage: true,
        },
        {
            trigger: ".o_pk_app[data-pk-app-shell]",
            run() {
                window.location.assign(window.sessionStorage.getItem("sc1542TeamUrl"));
            },
            expectUnloadPage: true,
        },
        {
            content: "« Brouillon restauré », compose re-opened with the text",
            trigger: '.o_pk_autosave[data-pk-autosave-restored="1"] .o_pk_draft_banner',
            run() {
                const value = document.querySelector("#sc_team_announcement").value;
                assert(value === DRAFT_TEXT, `restored value: ${value}`);
            },
        },
        {
            content: "Publish (the unchanged PRG form)",
            trigger: 'button[data-sc-action="team.announcement.publish"]',
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Published; the draft is gone",
            trigger: `.o_sc_announcement_body:contains(${DRAFT_TEXT})`,
            run() {
                assert(draftKeys().length === 0, `drafts left: ${draftKeys()}`);
                assert(!document.querySelector(".o_pk_draft_banner"), "restore banner shown");
            },
        },
    ],
});

tours.add("sc_1542_logout_clears_drafts", {
    steps: () => [
        {
            trigger: '[data-pk-edit-card="announcement"] button[data-pk-edit-toggle]',
            run: "click",
        },
        {
            trigger: "#sc_team_announcement",
            run: "edit Tour 1542 draft to forget",
        },
        {
            trigger: '.o_pk_autosave[data-pk-autosave-state="draft"]',
            run() {
                assert(draftKeys().length === 1, "expected one device draft");
                window.location.assign("/my/teams");
            },
            expectUnloadPage: true,
        },
        {
            content: "Open the user menu (task 1606: logout left « Plus »; task 1638: the app-bar avatar at every width)",
            trigger: "header.o_pk_appbar button[data-pk-user-menu-toggle]",
            run: "click",
        },
        {
            content: "« Se déconnecter »",
            trigger: '[data-pk-user-menu-popup]:not([hidden]) a[role="menuitem"][href^="/web/session/logout"]',
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "No draft left on the device",
            trigger: "body",
            run() {
                assert(draftKeys().length === 0, `drafts left: ${draftKeys()}`);
            },
        },
    ],
});

// Task 5201 (kit P6): the install page and the service worker kill switch
// tours are bemade_portal_kit_pwa's (pk_pwa_install_page,
// pk_pwa_sw_kill_switch).

// ------------------------------------------- fr_CA: OWL component strings
tours.add("sc_1542_fr_draft", {
    steps: () => [
        {
            trigger: '[data-pk-edit-card="announcement"] button[data-pk-edit-toggle]',
            run: "click",
        },
        {
            trigger: "#sc_team_announcement",
            run: "edit Brouillon de test 1542",
        },
        {
            content: "Save state in French (OWL template + _t)",
            trigger: '.o_pk_autosave[data-pk-autosave-state="draft"] .o_pk_save_state:contains(Brouillon gardé sur cet appareil)',
            run() {
                window.location.reload();
            },
            expectUnloadPage: true,
        },
        {
            content: "Restore banner in French",
            trigger: ".o_pk_draft_banner:contains(Brouillon restauré):contains(Jeter le brouillon)",
        },
    ],
});
