/**
 * Task 1385: lazy-load the recent-changes feed inside a homogenized portal
 * card's expandable <details>.
 *
 * The batched presence query at page render only flags WHICH cards changed (the
 * "changements récents" hint + the static injury markers). The expensive
 * per-player mail-tracking change compute runs here — once, the first time the
 * user actually opens a card — via the /my/player/<id>/recent-changes route.
 *
 * Progressive enhancement: if this script never runs (or the fetch fails), the
 * server-rendered fallback link to the full /my/player page stays usable.
 */
(function () {
    "use strict";

    function loadRecentChanges(container) {
        if (!container || container.getAttribute("data-loaded") === "1") {
            return;
        }
        var playerId = container.getAttribute("data-player-id");
        if (!playerId) {
            return;
        }
        // Mark loaded up front so a rapid open/close/open cannot fire twice.
        container.setAttribute("data-loaded", "1");
        var content = container.querySelector(".o_sc_recent_changes_content");
        var fallback = container.querySelector(".o_sc_recent_changes_fallback");
        fetch("/my/player/" + encodeURIComponent(playerId) + "/recent-changes", {
            headers: { "X-Requested-With": "XMLHttpRequest" },
        })
            .then(function (resp) {
                if (!resp.ok) {
                    throw new Error("HTTP " + resp.status);
                }
                return resp.text();
            })
            .then(function (html) {
                if (content) {
                    content.innerHTML = html;
                }
                // Task 1388: hide-on-empty-feed backstop. The server gate only
                // shows this block when player_changed is true, but that flag can
                // be true while the deduped feed is actually empty (#1387 net-no-op
                // edge). The fragment then renders only its "no tracked changes"
                // placeholder and no change <li> items — the same empty-feed signal
                // the fetch returns. Suppress the whole block so no "recent changes"
                // pill/heading ever shows over an empty feed.
                var hasItems = content && content.querySelector("li");
                if (!hasItems) {
                    container.classList.add("d-none");
                    return;
                }
                if (fallback) {
                    fallback.classList.add("d-none");
                }
            })
            .catch(function () {
                // Leave the fallback link visible; allow a later retry on re-open.
                container.setAttribute("data-loaded", "0");
            });
    }

    function bind(details) {
        // The <details> "toggle" event does not bubble, so we bind per element
        // rather than delegate. Cards are server-rendered, so they are all in the
        // DOM at init (inactive tabs included).
        details.addEventListener("toggle", function () {
            if (details.open) {
                loadRecentChanges(details.querySelector(".o_sc_recent_changes"));
            }
        });
    }

    function init() {
        var nodes = document.querySelectorAll("details.o_sc_card_detail");
        Array.prototype.forEach.call(nodes, bind);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
