/**
 * Task 1412: the clinic dossier's injury modal (#clinicInjuryModal).
 *
 * « Add injury » and each active-injury title / « Edit » are plain links to
 * the full pages (the no-JS path, #1410 breadcrumbs back) that ALSO carry
 * data-bs-toggle="modal" + data-fragment-url. Bootstrap's data API opens the
 * one modal shell; this script listens to show.bs.modal, reads the trigger
 * (event.relatedTarget), fetches its fragment (same-origin, credentials —
 * the fragment routes re-check access and are never cached) and injects the
 * form. The form then submits as a normal POST: the create / save handlers
 * redirect back to this clinic, same patient, the card in view.
 *
 * Failure ⇒ the translated error block (rendered by the page) with a link to
 * the trigger's full page. hidden.bs.modal resets the body so the next open
 * always re-fetches (no stale form).
 *
 * Vanilla, self-contained, in the style of the addon's other portal scripts
 * (portal_digest_history.js is the lazy-load precedent).
 */
(function () {
    "use strict";

    function showTitle(modal, kind) {
        var titles = modal.querySelectorAll(".o_sc_injury_modal_title");
        Array.prototype.forEach.call(titles, function (node) {
            node.classList.toggle("d-none", node.getAttribute("data-kind") !== kind);
        });
    }

    function showError(modal, fallbackUrl) {
        var body = modal.querySelector(".o_sc_injury_modal_body");
        var error = modal.querySelector(".o_sc_injury_modal_error");
        if (!body || !error) {
            return;
        }
        var clone = error.cloneNode(true);
        clone.classList.remove("d-none");
        var link = clone.querySelector(".o_sc_injury_modal_fallback");
        if (link) {
            if (fallbackUrl) {
                link.setAttribute("href", fallbackUrl);
            } else {
                link.classList.add("d-none");
            }
        }
        body.innerHTML = "";
        body.appendChild(clone);
    }

    function initForm(body) {
        // The fragment has no DOMContentLoaded script: mirror its N/A init.
        var na = body.querySelector("#injury_date_na");
        var date = body.querySelector("#injury_date");
        if (na && date) {
            date.required = !na.checked;
            date.disabled = na.checked;
        }
        var first = body.querySelector(
            "input:not([type=hidden]):not([disabled]), select, textarea");
        if (first && typeof first.focus === "function") {
            try {
                first.focus();
            } catch (_e) {
                // best effort
            }
        }
    }

    function load(modal, trigger) {
        var body = modal.querySelector(".o_sc_injury_modal_body");
        if (!body) {
            return;
        }
        var url = trigger.getAttribute("data-fragment-url");
        var fallbackUrl = trigger.getAttribute("href");
        resetBody(modal);
        if (!url) {
            showError(modal, fallbackUrl);
            return;
        }
        // Ignore the answer of an earlier, slower fetch (rapid open/close/open).
        var token = String(Date.now()) + Math.random();
        modal.setAttribute("data-load-token", token);
        fetch(url, {
            credentials: "same-origin",
            headers: { "X-Requested-With": "XMLHttpRequest" },
        })
            .then(function (resp) {
                if (!resp.ok) {
                    throw new Error("HTTP " + resp.status);
                }
                return resp.text();
            })
            .then(function (html) {
                if (modal.getAttribute("data-load-token") !== token) {
                    return;
                }
                body.innerHTML = html;
                initForm(body);
            })
            .catch(function () {
                if (modal.getAttribute("data-load-token") !== token) {
                    return;
                }
                showError(modal, fallbackUrl);
            });
    }

    function resetBody(modal) {
        var body = modal.querySelector(".o_sc_injury_modal_body");
        if (!body) {
            return;
        }
        var placeholder = modal.getAttribute("data-placeholder-html");
        if (placeholder === null) {
            placeholder = body.innerHTML;
            modal.setAttribute("data-placeholder-html", placeholder);
        }
        body.innerHTML = placeholder;
    }

    function bind(modal) {
        if (modal.getAttribute("data-injury-modal-bound")) {
            return;
        }
        modal.setAttribute("data-injury-modal-bound", "1");
        // remember the pristine « Loading… » body once, before anything runs
        resetBody(modal);
        modal.addEventListener("show.bs.modal", function (ev) {
            var trigger = ev.relatedTarget;
            if (!trigger || !trigger.classList || !trigger.classList.contains("o_sc_injury_modal_link")) {
                return;
            }
            showTitle(modal, trigger.getAttribute("data-modal-kind") || "edit");
            load(modal, trigger);
        });
        modal.addEventListener("hidden.bs.modal", function () {
            modal.removeAttribute("data-load-token");
            resetBody(modal);
        });
    }

    function init() {
        var nodes = document.querySelectorAll(".o_sc_injury_modal");
        Array.prototype.forEach.call(nodes, bind);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
