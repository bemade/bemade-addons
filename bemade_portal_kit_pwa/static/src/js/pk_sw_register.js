/*
 * Task 5201 (kit P6) — the installable app's page script (moved from the
 * first consumer, task 1542 / 1543): the service worker registration, the
 * kill switch and the « Install the app » page.
 *
 * - Inside the app shell (.o_pk_app[data-pk-app-shell]): register
 *   /my/service-worker.js with scope "/" (the whole origin, so the
 *   language-prefixed pages such as /en/my/... are in the app too).
 * - Anywhere else (this bundle loads on every frontend page): if the device
 *   still holds ANY registration of this worker script, whatever its scope,
 *   ask the server for the worker; a 404 means the switch is OFF ->
 *   unregister them all (the kill switch). A buggy or retired worker can
 *   never stay stuck on a device.
 * - Install page: « The app is installed » in standalone mode; the
 *   browser's own install prompt button when the browser offers it
 *   (Android / Chrome / Edge). No banner anywhere.
 *
 * <html data-pk-sw="registered|unregistered|none"> is set for the tours.
 */
export const PK_SW_URL = "/my/service-worker.js";
export const PK_SW_SCOPE = "/";
const SHELL = ".o_pk_app[data-pk-app-shell]";

function mark(state) {
    document.documentElement.setAttribute("data-pk-sw", state);
}

/** Does registration ``reg`` run OUR script (any scope)? */
export function pkSwIsMine(reg) {
    return [reg.active, reg.waiting, reg.installing].some((worker) => {
        try {
            return Boolean(worker) && new URL(worker.scriptURL).pathname === PK_SW_URL;
        } catch {
            return false;
        }
    });
}

/**
 * The kill switch: every registration of our worker is removed when the
 * worker's URL answers 404. ``container`` / ``fetchFn``: injectable for the
 * tests. Resolves to the new ``data-pk-sw`` state (or undefined).
 */
export async function pkSwKillSwitch(container = navigator.serviceWorker, fetchFn = fetch) {
    try {
        const mine = (await container.getRegistrations()).filter(pkSwIsMine);
        if (!mine.length) {
            mark("none");
            return "none";
        }
        const resp = await fetchFn(PK_SW_URL, { cache: "no-store", credentials: "same-origin" });
        if (resp.status !== 404) {
            return undefined;
        }
        await Promise.all(mine.map((reg) => reg.unregister()));
        mark("unregistered");
        return "unregistered";
    } catch {
        // offline: try again on the next page load
        return undefined;
    }
}

function register() {
    navigator.serviceWorker
        .register(PK_SW_URL, { scope: PK_SW_SCOPE })
        .then(() => navigator.serviceWorker.ready)
        .then(() => mark("registered"))
        .catch(() => pkSwKillSwitch());
}

// ---------------------------------------------------------- install page
let deferredPrompt = null;
window.addEventListener("beforeinstallprompt", (ev) => {
    ev.preventDefault();
    deferredPrompt = ev;
    const section = document.querySelector('[data-pk-install-state="prompt"]');
    if (section) {
        section.hidden = false;
    }
});

/** Is the page running as an installed app? */
export function pkIsStandalone(win = window) {
    return Boolean(
        (win.matchMedia && win.matchMedia("(display-mode: standalone)").matches) ||
            win.navigator.standalone === true
    );
}

/** The install page: the « installed » state in standalone mode (the steps
 * hidden). Returns whether the page is there. */
export function pkInitInstallPage(root = document, standalone = pkIsStandalone()) {
    if (!root.querySelector("[data-pk-install]")) {
        return false;
    }
    if (standalone) {
        const done = root.querySelector('[data-pk-install-state="installed"]');
        if (done) {
            done.hidden = false;
        }
        root.querySelectorAll("[data-pk-install-steps]").forEach((el) => {
            el.hidden = true;
        });
    }
    return true;
}

document.addEventListener("click", (ev) => {
    const button = ev.target.closest && ev.target.closest("[data-pk-install-prompt]");
    if (!button || !deferredPrompt) {
        return;
    }
    deferredPrompt.prompt();
    deferredPrompt.userChoice.then(() => {
        deferredPrompt = null;
        button.closest("section").hidden = true;
    });
});

function init() {
    pkInitInstallPage();
    if (!("serviceWorker" in navigator)) {
        return;
    }
    if (document.querySelector(SHELL)) {
        register();
    } else {
        pkSwKillSwitch();
    }
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
} else {
    init();
}
