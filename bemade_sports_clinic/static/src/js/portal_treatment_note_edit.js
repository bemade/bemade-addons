/**
 * Task 1413: the inline « Edit » form of a treatment note (clinic notes
 * table + player page notes tab).
 *
 * The form lives in a <details> element, so « Edit » opens it and the
 * summary closes it without any script. This only wires « Cancel »: close
 * the <details> and reset the form to the stored values, so an abandoned
 * edit never lingers. Progressive enhancement — vanilla, in the style of the
 * addon's other portal scripts.
 */
(function () {
    "use strict";

    function onClick(event) {
        var button = event.target.closest(".o_sc_note_edit_cancel");
        if (!button) {
            return;
        }
        event.preventDefault();
        var form = button.closest("form");
        if (form) {
            form.reset();
        }
        var details = button.closest("details.o_sc_note_edit");
        if (details) {
            details.open = false;
            var summary = details.querySelector("summary");
            if (summary) {
                summary.focus();
            }
        }
    }

    function init() {
        if (document.body.getAttribute("data-note-edit-bound")) {
            return;
        }
        document.body.setAttribute("data-note-edit-bound", "1");
        document.body.addEventListener("click", onClick);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
