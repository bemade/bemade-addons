/**
 * Task 1398: desktop drag-reorder for the clinic worklist at /my/clinic/<id>.
 *
 * DESKTOP ONLY, ON PURPOSE (owner decision 2026-08-17). This is the plain HTML5
 * drag-and-drop API and nothing else — no Pointer-Events/touch-drag machinery,
 * which was explicitly not wanted. If dragging does nothing on a phone, that is
 * the accepted outcome: the up/down buttons rendered on every row are the
 * reorder path there, and they are also the keyboard-accessible path and the
 * no-JS path. This file is therefore pure progressive enhancement — if it never
 * runs, the page loses nothing but the drag.
 *
 * Only the grip (.o_sc_drag_handle) is draggable, so clicking anywhere else on
 * a row still follows the link and selects that patient in the dossier pane.
 *
 * Persistence is ONE POST after the drop (not one per intermediate move): the
 * final id order is written into the hidden reorder form and submitted, and the
 * server recomputes `sequence`. The form carries the currently selected patient
 * so the dossier survives the round trip.
 *
 * Style precedent: the addon's other portal scripts (portal_card_recent_changes.js,
 * portal_digest_history.js) — small, vanilla, self-contained, no framework.
 */
(function () {
    "use strict";

    var DRAGGING_CLASS = "o_sc_dragging";
    var OVER_CLASS = "o_sc_drag_over";

    function rowOf(node) {
        return node && node.closest ? node.closest(".o_sc_worklist_row") : null;
    }

    function clearOver(list) {
        var marked = list.querySelectorAll("." + OVER_CLASS);
        Array.prototype.forEach.call(marked, function (el) {
            el.classList.remove(OVER_CLASS);
        });
    }

    function submitOrder(list) {
        var form = document.getElementById("clinic_reorder_form");
        if (!form) {
            return;
        }
        var input = form.querySelector('input[name="order"]');
        if (!input) {
            return;
        }
        var ids = [];
        var rows = list.querySelectorAll(".o_sc_worklist_row");
        Array.prototype.forEach.call(rows, function (row) {
            var id = row.getAttribute("data-attendance-id");
            if (id) {
                ids.push(id);
            }
        });
        if (!ids.length) {
            return;
        }
        input.value = ids.join(",");
        form.submit();
    }

    function bind(list) {
        var dragged = null;

        // The handle is what carries draggable="true"; the row it lives in is
        // what actually moves.
        list.addEventListener("dragstart", function (ev) {
            var handle = ev.target.closest && ev.target.closest(".o_sc_drag_handle");
            if (!handle) {
                return;
            }
            dragged = rowOf(handle);
            if (!dragged) {
                return;
            }
            dragged.classList.add(DRAGGING_CLASS);
            if (ev.dataTransfer) {
                ev.dataTransfer.effectAllowed = "move";
                // Firefox refuses to start a drag without payload.
                ev.dataTransfer.setData("text/plain", dragged.getAttribute("data-attendance-id") || "");
                ev.dataTransfer.setDragImage(dragged, 0, 0);
            }
        });

        list.addEventListener("dragover", function (ev) {
            if (!dragged) {
                return;
            }
            var target = rowOf(ev.target);
            if (!target || target === dragged) {
                return;
            }
            // preventDefault is what makes this a valid drop target.
            ev.preventDefault();
            if (ev.dataTransfer) {
                ev.dataTransfer.dropEffect = "move";
            }
            clearOver(list);
            target.classList.add(OVER_CLASS);
            // Insert above or below depending on which half we are over, so the
            // list previews the result before the drop.
            var box = target.getBoundingClientRect();
            var below = ev.clientY > box.top + box.height / 2;
            if (below) {
                target.parentNode.insertBefore(dragged, target.nextSibling);
            } else {
                target.parentNode.insertBefore(dragged, target);
            }
        });

        list.addEventListener("drop", function (ev) {
            if (!dragged) {
                return;
            }
            ev.preventDefault();
            clearOver(list);
            dragged.classList.remove(DRAGGING_CLASS);
            dragged = null;
            // ONE post, here, with the final order.
            submitOrder(list);
        });

        list.addEventListener("dragend", function () {
            clearOver(list);
            if (dragged) {
                dragged.classList.remove(DRAGGING_CLASS);
                dragged = null;
            }
        });
    }

    function init() {
        var lists = document.querySelectorAll(".o_sc_worklist");
        Array.prototype.forEach.call(lists, bind);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
