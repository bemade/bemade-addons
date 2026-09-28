/*
 * Task 1542 (epic #1535) — installable app: service worker registration,
 * the kill switch and the « Installer l'application » page.
 *
 * - Inside the app shell: register /my/service-worker.js (scope /my/).
 * - Anywhere else (this bundle loads on every frontend page): if the device
 *   still holds a /my/ registration, ask the server for the worker; a 404
 *   means the system switch is OFF -> unregister it (the kill switch). A
 *   buggy or retired worker can therefore never stay stuck on a phone.
 * - Install page: « L'application est installée » in standalone mode; the
 *   browser's own install prompt button when the browser offers it
 *   (Android / Chrome / Edge). No banner anywhere.
 *
 * <html data-sc-sw="registered|unregistered"> is set for the tours.
 */
(function () {
    "use strict";

    var SW_URL = "/my/service-worker.js";
    var SCOPE = "/my/";

    function mark(state) {
        document.documentElement.setAttribute("data-sc-sw", state);
    }

    function myRegistrations() {
        return navigator.serviceWorker.getRegistrations().then(function (regs) {
            return regs.filter(function (reg) {
                try {
                    return new URL(reg.scope).pathname === SCOPE;
                } catch (_err) {
                    return false;
                }
            });
        });
    }

    function killSwitch() {
        return myRegistrations()
            .then(function (mine) {
                if (!mine.length) {
                    mark("none");
                    return;
                }
                return fetch(SW_URL, { cache: "no-store", credentials: "same-origin" }).then(
                    function (resp) {
                        if (resp.status !== 404) {
                            return;
                        }
                        return Promise.all(
                            mine.map(function (reg) {
                                return reg.unregister();
                            })
                        ).then(function () {
                            mark("unregistered");
                        });
                    }
                );
            })
            .catch(function () {
                // offline: try again on the next page load
            });
    }

    function register() {
        navigator.serviceWorker
            .register(SW_URL, { scope: SCOPE })
            .then(function () {
                return navigator.serviceWorker.ready;
            })
            .then(function () {
                mark("registered");
            })
            .catch(function () {
                killSwitch();
            });
    }

    // ------------------------------------------------------ install page
    var deferredPrompt = null;
    window.addEventListener("beforeinstallprompt", function (ev) {
        ev.preventDefault();
        deferredPrompt = ev;
        var section = document.querySelector('[data-sc-install-state="prompt"]');
        if (section) {
            section.hidden = false;
        }
    });

    function initInstallPage() {
        var hero = document.querySelector("[data-sc-install]");
        if (!hero) {
            return;
        }
        var standalone =
            (window.matchMedia && window.matchMedia("(display-mode: standalone)").matches) ||
            window.navigator.standalone === true;
        if (standalone) {
            var done = document.querySelector('[data-sc-install-state="installed"]');
            if (done) {
                done.hidden = false;
            }
            document.querySelectorAll("[data-sc-install-steps]").forEach(function (el) {
                el.hidden = true;
            });
        }
        document.addEventListener("click", function (ev) {
            var button = ev.target.closest && ev.target.closest("[data-sc-install-prompt]");
            if (!button || !deferredPrompt) {
                return;
            }
            deferredPrompt.prompt();
            deferredPrompt.userChoice.then(function () {
                deferredPrompt = null;
                button.closest("section").hidden = true;
            });
        });
    }

    function init() {
        initInstallPage();
        if (!("serviceWorker" in navigator)) {
            return;
        }
        if (document.querySelector(".o_sc_app[data-sc-app-shell]")) {
            register();
        } else {
            killSwitch();
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
