/**
 * Task 1389: lazy-load the daily-digest snapshot history inside the portal
 * team-dashboard "Historique" modal.
 *
 * The team dashboard renders only an empty modal shell. The first time the user
 * opens it, this fetches the recent-slice fragment (last 14 days) from
 * /my/team/<id>/digest-history/recent and injects it into the modal body. The
 * fragment carries its own "Voir tout l'historique" link (a normal navigation
 * to the full paginated page), so no in-modal pager is needed.
 *
 * Mirrors the portal_card_recent_changes.js lazy-load pattern: mark loaded up
 * front so a rapid open/close/open cannot double-fetch; on failure, clear the
 * flag so a later re-open retries. Progressive enhancement — if this never runs,
 * the modal simply shows its "Chargement…" placeholder; the feature also lives
 * on its own /digest-history URL reachable server-side.
 */
(function () {
    "use strict";

    function loadHistory(body) {
        if (!body || body.getAttribute("data-loaded") === "1") {
            return;
        }
        var url = body.getAttribute("data-history-url");
        if (!url) {
            return;
        }
        // Mark loaded up front so a rapid open/close/open cannot fire twice.
        body.setAttribute("data-loaded", "1");
        fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } })
            .then(function (resp) {
                if (!resp.ok) {
                    throw new Error("HTTP " + resp.status);
                }
                return resp.text();
            })
            .then(function (html) {
                body.innerHTML = html;
            })
            .catch(function () {
                // Allow a retry on the next open; leave the placeholder visible.
                body.setAttribute("data-loaded", "0");
            });
    }

    function bind(modal) {
        // Bootstrap 5 fires show.bs.modal on the modal root when it opens.
        modal.addEventListener("show.bs.modal", function () {
            loadHistory(modal.querySelector(".o_sc_digest_history_body"));
        });
    }

    function init() {
        var nodes = document.querySelectorAll("[id^='teamDigestHistoryModal']");
        Array.prototype.forEach.call(nodes, bind);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
