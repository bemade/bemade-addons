/*
 * Review fixes 2026-10-18 b — the player Documents tab's picker (the
 * injury card's, shared) in a browser. Run by
 * tests/test_review_fixes_tours_1018b.py (phone 390 px, laptop 1366 px).
 * Synthetic data; language-independent triggers.
 *
 * sc_1018b_player_documents: « + Ajouter » opens the upload panel; files
 * chosen in two goes add up (a duplicate ignored); each row is pre-filled
 * with the shared category / description; a row's own description /
 * category / name change only that file; an injury is linked; one upload
 * posts every file with its own values. Round 2 (1018c): the shared
 * fields ([data-sc-doc-shared-group]) show only while no file is listed —
 * hidden from the first row on, shown again once the list is emptied.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function setFiles(input, files) {
    const transfer = new DataTransfer();
    for (const file of files) {
        transfer.items.add(file);
    }
    input.files = transfer.files;
    input.dispatchEvent(new Event("change", { bubbles: true }));
}

function setValue(el, value) {
    el.focus();
    el.value = value;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    el.blur();
    el.dispatchEvent(new FocusEvent("blur")); // headless CI
}

const PANEL = "details#sc_documents_upload";
const FORM = `${PANEL} form[data-sc-doc-upload]`;

function rows() {
    return [...document.querySelectorAll(`${FORM} [data-sc-file-list] li.o_sc_file`)];
}

function sharedShown() {
    const group = document.querySelector(`${FORM} [data-sc-doc-shared-group]`);
    assert(group, "no shared group");
    return !group.hidden && group.getBoundingClientRect().height > 0;
}

function row(name) {
    return rows().find((li) => li.querySelector(".o_sc_file_name").textContent === name);
}

tours.add("sc_1018b_player_documents", {
    steps: () => [
        {
            content: "« + Ajouter » of the Documents list",
            trigger: '.o_sc_list_header button.o_sc_list_add[aria-controls="sc_documents_upload"]',
            run: "click",
        },
        {
            content: "1018c: the shared fields are never shown (empty list, a row, emptied again)",
            trigger: `${PANEL}[open] form[data-sc-doc-upload] .o_sc_dropzone`,
            run() {
                const form = document.querySelector(FORM);
                assert(!sharedShown(), "shared fields shown on an empty list");
                setFiles(form.querySelector('input[type="file"]'), [
                    new File(["synthetic x"], "Synthetic x.pdf", { type: "application/pdf", lastModified: 9 }),
                ]);
                assert(rows().length === 1, "one row");
                assert(!sharedShown(), "shared fields still shown with a file listed");
                row("Synthetic x.pdf").querySelector("button[data-sc-file-remove]").click();
                assert(rows().length === 0, "x not removed");
                assert(!sharedShown(), "shared fields shown again on an emptied list");
            },
        },
        {
            content: "Shared values, then the first file",
            trigger: `${PANEL}[open] form[data-sc-doc-upload] .o_sc_dropzone`,
            run() {
                const form = document.querySelector(FORM);
                setValue(form.querySelector('select[name="category"]'), "prescription");
                setValue(form.querySelector('textarea[name="description"]'), "Synthetic shared one");
                setFiles(form.querySelector('input[type="file"]'), [
                    new File(["synthetic a"], "Synthetic a.pdf", { type: "application/pdf", lastModified: 1 }),
                ]);
                assert(rows().length === 1, "one row");
            },
        },
        {
            content: "More files (shared fields hidden): pre-filled with the shared values",
            trigger: `${FORM} [data-sc-file-row]`,
            run() {
                const form = document.querySelector(FORM);
                assert(!sharedShown(), "shared fields shown with a file listed");
                setFiles(form.querySelector('input[type="file"]'), [
                    new File(["synthetic b"], "Synthetic b.pdf", { type: "application/pdf", lastModified: 2 }),
                    new File(["synthetic a"], "Synthetic a.pdf", { type: "application/pdf", lastModified: 1 }),
                ]);
                assert(rows().length === 2, `rows: ${rows().length} (duplicate not ignored?)`);
                assert(form.querySelector('input[type="file"]').files.length === 2, "input not rebuilt");
                const a = row("Synthetic a.pdf");
                const b = row("Synthetic b.pdf");
                assert(a.querySelector('[name="doc_description"]').value === "Synthetic shared one", "a rewritten");
                assert(b.querySelector('[name="doc_description"]').value === "Synthetic shared one", "b prefill");
                assert(b.querySelector('[name="doc_category"]').value === "prescription", "b category");
                assert(a.querySelector('[name="doc_name"]').value === "Synthetic a.pdf", "a name prefill");
            },
        },
        {
            content: "One row's own values; they survive a re-render (a third file)",
            trigger: `${FORM} [data-sc-file-row]`,
            run() {
                const a = row("Synthetic a.pdf");
                setValue(a.querySelector('[name="doc_description"]'), "Synthetic only a");
                setValue(a.querySelector('[name="doc_category"]'), "medical_imaging");
                setValue(a.querySelector('[name="doc_name"]'), "Synthetic A report");
                const form = document.querySelector(FORM);
                setFiles(form.querySelector('input[type="file"]'), [
                    new File(["synthetic c"], "Synthetic c.pdf", { type: "application/pdf", lastModified: 3 }),
                ]);
                assert(rows().length === 3, "three rows");
                const again = row("Synthetic a.pdf");
                assert(again.querySelector('[name="doc_description"]').value === "Synthetic only a", "a lost");
                assert(row("Synthetic b.pdf").querySelector('[name="doc_description"]').value
                    === "Synthetic shared one", "b changed by a");
                // « × » drops c.
                row("Synthetic c.pdf").querySelector("button[data-sc-file-remove]").click();
                assert(rows().length === 2, "c not removed");
                assert(!sharedShown(), "shared fields shown with files listed");
                // Phone: a row never overflows the page.
                const doc = document.documentElement;
                assert(doc.scrollWidth <= window.innerWidth + 1, `overflow ${doc.scrollWidth}`);
                if (window.innerWidth < 576) {
                    const fields = row("Synthetic a.pdf").querySelectorAll(".o_sc_file_field");
                    assert(fields[0].getBoundingClientRect().top < fields[1].getBoundingClientRect().top,
                        "row not stacked on a phone");
                }
                // Link the injury.
                const injury = form.querySelector('select[name="injury_id"]');
                setValue(injury, injury.options[1].value);
            },
        },
        {
            content: "Upload",
            trigger: `${FORM} button[type="submit"]`,
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Back on the Documents tab with both documents",
            trigger: '[data-sc-section="player.documents"]',
            run() {
                const text = document.querySelector('[data-sc-section="player.documents"]').textContent;
                for (const name of ["Synthetic A report", "Synthetic b.pdf"]) {
                    assert(text.includes(name), `${name} missing`);
                }
            },
        },
    ],
});
