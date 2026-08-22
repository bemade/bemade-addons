/**
 * Task 1397: keep the clinic worklist at /my/clinic/<id> fresh while the
 * therapist works — the kiosk (#1397) writes rows from an iPad the therapist
 * never touches, so the list must update by itself.
 *
 * Pure progressive enhancement, in the style of the addon's other portal
 * scripts (vanilla, self-contained): every 20 s, while the tab is VISIBLE,
 * GET /my/clinic/<id>/worklist/fragment (the worklist <ul> alone, rendered
 * server-side by the same template and the same access checks as the page)
 * and swap the rows in. Without this script a reload shows the same thing.
 *
 * What is preserved across a swap:
 *  - the selected patient highlight (the fragment is asked for ?patient=,
 *    read from the list's data-selected-patient);
 *  - the drag-reorder listeners (portal_clinic_reorder.js binds on the <ul>,
 *    and only the <ul>'s CHILDREN are replaced);
 *  - a drag in progress (no swap while a row is .o_sc_dragging);
 *  - the header badge count and the #1399 counts line (data-count /
 *    data-counts-line on the fragment's <ul>).
 *
 * Also here: the « Copy » button of the kiosk panel (navigator.clipboard;
 * the read-only input selects itself on click as the no-JS fallback).
 */
(function () {
    "use strict";

    var POLL_MS = 20000;

    function fragmentUrl(list) {
        var clinicId = list.getAttribute("data-clinic-id");
        var selected = list.getAttribute("data-selected-patient") || "";
        var url = "/my/clinic/" + encodeURIComponent(clinicId) + "/worklist/fragment";
        if (selected) {
            url += "?patient=" + encodeURIComponent(selected);
        }
        return url;
    }

    function applyFragment(list, html) {
        var parser = new DOMParser();
        var doc = parser.parseFromString(html, "text/html");
        var fresh = doc.querySelector("ul.o_sc_worklist");
        if (!fresh) {
            return;
        }
        // Children only: the <ul> keeps its identity (and its listeners).
        list.innerHTML = fresh.innerHTML;
        list.setAttribute("data-count", fresh.getAttribute("data-count") || "0");
        list.setAttribute("data-counts-line", fresh.getAttribute("data-counts-line") || "");

        var card = list.closest(".card");
        var badge = card ? card.querySelector(".card-header .badge") : null;
        if (badge) {
            badge.textContent = fresh.getAttribute("data-count") || "0";
        }
        var countsText = document.getElementById("clinic-attendance-counts-text");
        var countsBox = document.getElementById("clinic-attendance-counts");
        if (countsText && countsBox) {
            var line = fresh.getAttribute("data-counts-line") || "";
            countsText.textContent = line;
            countsBox.classList.toggle("d-none", !line);
        }
    }

    function refresh(list) {
        if (document.visibilityState !== "visible") {
            return;
        }
        if (list.querySelector(".o_sc_dragging")) {
            return;
        }
        var xhr = new XMLHttpRequest();
        xhr.open("GET", fragmentUrl(list), true);
        xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");
        xhr.setRequestHeader("Cache-Control", "no-store");
        xhr.onload = function () {
            if (xhr.status === 200 && xhr.responseText) {
                applyFragment(list, xhr.responseText);
            }
            // 403 / 404 / 500: keep what is on screen; the next poll retries.
        };
        xhr.send();
    }

    function bindRefresh(list) {
        if (list.getAttribute("data-refresh-bound")) {
            return;
        }
        list.setAttribute("data-refresh-bound", "1");
        window.setInterval(function () {
            refresh(list);
        }, POLL_MS);
        // Coming back to the tab: refresh at once rather than waiting a cycle.
        document.addEventListener("visibilitychange", function () {
            if (document.visibilityState === "visible") {
                refresh(list);
            }
        });
    }

    function bindCopy(button) {
        if (button.getAttribute("data-copy-bound")) {
            return;
        }
        button.setAttribute("data-copy-bound", "1");
        button.addEventListener("click", function () {
            var target = document.getElementById(button.getAttribute("data-copy-target"));
            if (!target) {
                return;
            }
            var label = button.querySelector(".o_sc_kiosk_copy_label");
            var original = label ? label.textContent : "";
            var done = function () {
                if (label) {
                    label.textContent = button.getAttribute("data-copied-label") || original;
                    window.setTimeout(function () { label.textContent = original; }, 2000);
                }
            };
            target.select();
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(target.value).then(done, function () {
                    try { document.execCommand("copy"); done(); } catch (e) { /* leave it selected */ }
                });
            } else {
                try { document.execCommand("copy"); done(); } catch (e) { /* leave it selected */ }
            }
        });
    }

    function init() {
        var lists = document.querySelectorAll("ul.o_sc_worklist[data-clinic-id]");
        Array.prototype.forEach.call(lists, bindRefresh);
        var copies = document.querySelectorAll(".o_sc_kiosk_copy[data-copy-target]");
        Array.prototype.forEach.call(copies, bindCopy);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
