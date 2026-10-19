/*
 * Task 1616 — the injury card in three sections in a browser. Run by
 * tests/test_injury_card_tours_1616.py (phone 390 px and laptop 1366 px).
 * Synthetic data; language-independent triggers.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

async function waitFor(check, message, timeout = 8000) {
    const start = Date.now();
    while (!check()) {
        if (Date.now() - start > timeout) {
            throw new Error(`timeout: ${message}`);
        }
        await new Promise((resolve) => setTimeout(resolve, 100));
    }
}

function typeAndLeave(input, value) {
    input.focus();
    input.value = value;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
    input.blur();
    input.dispatchEvent(new FocusEvent("blur")); // headless CI: blur() fires no event without window focus
}

const CARD = "details.o_sc_injury_item[open]";
const DETAILS = `${CARD} section[data-sc-edit-card="injury-details"]`;
const NOTES = `${CARD} section[data-sc-edit-card="injury-notes"]`;
const DOCS = `${CARD} section[data-sc-section="injury.documents"]`;
const ADD_SHEET = 'dialog[id$="_documents_add"]';

function el(selector) {
    return document.querySelector(selector);
}

function editShown(section) {
    return !el(`${section} [data-sc-edit-view="edit"]`).hidden;
}

function setFiles(input, files) {
    const transfer = new DataTransfer();
    for (const file of files) {
        transfer.items.add(file);
    }
    input.files = transfer.files;
    input.dispatchEvent(new Event("change", { bubbles: true }));
}

// ------------------------------------------- three sections, one pencil each
tours.add("sc_1616_card_sections", {
    steps: () => [
        {
            content: "The open card: Details, Notes, Documents — laid out for the screen",
            trigger: `${CARD} .o_sc_injury_sections`,
            run() {
                const box = (selector) => el(selector).getBoundingClientRect();
                const details = box(DETAILS);
                const notes = box(NOTES);
                const docs = box(DOCS);
                if (window.innerWidth >= 992) {
                    assert(notes.left > details.right - 1, "laptop: Notes right of Details");
                    assert(Math.abs(docs.left - details.left) < 2, "laptop: Documents under Details");
                    assert(docs.top >= details.bottom - 1, "laptop: Documents below Details");
                    assert(notes.top < docs.top, "laptop: Notes starts beside Details");
                } else {
                    assert(details.bottom <= notes.top + 1, "phone: Details then Notes");
                    assert(notes.bottom <= docs.top + 1, "phone: Notes then Documents");
                    assert(Math.abs(details.left - notes.left) < 2, "phone: one column");
                }
                assert(!editShown(DETAILS) && !editShown(NOTES), "read views first");
            },
        },
        {
            content: "The Details pencil edits Details only",
            trigger: `${DETAILS} button[data-sc-edit-toggle]`,
            run: "click",
        },
        {
            content: "Details in edit mode, Notes still reading",
            trigger: `${DETAILS}[data-sc-edit-open] [data-sc-edit-view="edit"]:not([hidden])`,
            run() {
                assert(!editShown(NOTES), "Notes opened too");
                assert(el(`${DETAILS} .o_sc_autosave[data-sc-field="stage"]`), "status in Details");
                assert(!el(`${DETAILS} .o_sc_autosave[data-sc-field="external_notes"]`), "notes in Details");
            },
        },
        {
            content: "Details « Done »",
            trigger: `${DETAILS} [data-sc-edit-done]`,
            run: "click",
        },
        {
            content: "The Notes pencil edits the notes only",
            trigger: `${DETAILS}:not([data-sc-edit-open]) [data-sc-edit-view="read"]:not([hidden])`,
            run() {
                el(`${NOTES} button[data-sc-edit-toggle]`).click();
            },
        },
        {
            content: "Notes in edit mode (both notes), Details reading",
            trigger: `${NOTES}[data-sc-edit-open] .o_sc_autosave[data-sc-field="internal_notes"]`,
            run() {
                assert(!editShown(DETAILS), "Details opened too");
                assert(el(`${NOTES} .o_sc_autosave[data-sc-field="external_notes"]`), "external notes");
            },
        },
        {
            content: "The card's « Done » closes the groups and the card",
            trigger: `${CARD} [data-sc-injury-done]`,
            run: "click",
        },
        {
            content: "Closed",
            trigger: "details.o_sc_injury_item:not([open])",
            run() {
                assert(!document.querySelector(`${CARD}`), "a card is still open");
                assert(!document.querySelector('section[data-sc-edit-card="injury-notes"][data-sc-edit-open]'),
                    "the Notes group stayed in edit mode");
            },
        },
    ],
});

// --------------------------- several documents at once, then re-file one
tours.add("sc_1616_documents_upload", {
    steps: () => [
        {
            content: "« + Ajouter » in the card's Documents list header",
            trigger: `${DOCS} .o_sc_list_header button.o_sc_list_add[data-sc-action="injury.documents.add"]`,
            run: "click",
        },
        {
            content: "A file over 10 MB is flagged and blocks the upload",
            trigger: `${ADD_SHEET}[open] .o_sc_dropzone`,
            run() {
                window.__sc1616NoReload = "1";
                // Review fixes 2026-10-18 b: the shared category / description
                // pre-fill each file's row WHEN it is added — set them first.
                const form = this.anchor.closest("form");
                const category = form.querySelector('select[name="category"]');
                category.value = "medical_imaging";
                category.dispatchEvent(new Event("change", { bubbles: true }));
                form.querySelector('textarea[name="description"]').value = "Synthetic batch";
                setFiles(this.anchor.querySelector('input[type="file"][multiple]'), [
                    new File(["synthetic"], "Synthetic small.pdf", { type: "application/pdf" }),
                    new File([new Uint8Array(10 * 1024 * 1024 + 1)], "Synthetic big.pdf", {
                        type: "application/pdf",
                    }),
                ]);
                const sheet = el(`${ADD_SHEET}[open]`);
                assert(!sheet.querySelector("[data-sc-file-error]").hidden, "no error shown");
                const flagged = sheet.querySelectorAll('[data-sc-file-too-large="1"]');
                assert(flagged.length === 1 && flagged[0].textContent.includes("Synthetic big.pdf"), "flag");
                sheet.querySelector('button[type="submit"]').click();
            },
        },
        {
            content: "Nothing was sent (no reload); « × » drops the big file",
            trigger: `${ADD_SHEET}[open] [data-sc-file-too-large="1"] button[data-sc-file-remove]`,
            run() {
                assert(window.__sc1616NoReload === "1", "the oversized upload was posted");
                this.anchor.click();
                const sheet = el(`${ADD_SHEET}[open]`);
                assert(sheet.querySelector("[data-sc-file-error]").hidden, "error still shown");
                const names = [...sheet.querySelectorAll("[data-sc-file-list] .o_sc_file_name")].map((n) => n.textContent);
                assert(JSON.stringify(names) === JSON.stringify(["Synthetic small.pdf"]), `left: ${names}`);
                assert(sheet.querySelector('input[type="file"]').files.length === 1, "input not rebuilt");
            },
        },
        {
            content: "Review fixes 2026-10-18: choosing again ADDS (a, then b + a duplicate)",
            trigger: `${ADD_SHEET}[open] .o_sc_dropzone`,
            run() {
                const input = this.anchor.querySelector('input[type="file"]');
                const a = new File(["synthetic a"], "Synthetic a.pdf", { type: "application/pdf", lastModified: 1 });
                setFiles(input, [a]);
                setFiles(input, [
                    new File(["synthetic b"], "Synthetic b.pdf", { type: "application/pdf", lastModified: 2 }),
                    new File(["synthetic a"], "Synthetic a.pdf", { type: "application/pdf", lastModified: 1 }),
                ]);
                const sheet = el(`${ADD_SHEET}[open]`);
                assert(sheet.querySelector("[data-sc-file-error]").hidden, "error still shown");
                const names = [...sheet.querySelectorAll("[data-sc-file-list] .o_sc_file_name")].map((n) => n.textContent);
                assert(
                    JSON.stringify(names) === JSON.stringify(["Synthetic small.pdf", "Synthetic a.pdf", "Synthetic b.pdf"]),
                    `accumulated list: ${names}`
                );
                assert(input.files.length === 3, `input holds ${input.files.length} files`);
                assert(sheet.querySelectorAll("[data-sc-file-list] li button[data-sc-file-remove]").length === 3, "×");
                // Each row carries the shared values it was added with.
                const rows = [...sheet.querySelectorAll("[data-sc-file-list] [data-sc-file-row]")];
                assert(rows.length === 3, `rows: ${rows.length}`);
                for (const row of rows) {
                    assert(row.querySelector('[name="doc_category"]').value === "medical_imaging", "row category");
                    assert(row.querySelector('[name="doc_description"]').value === "Synthetic batch", "row text");
                }
            },
        },
        {
            content: "Upload",
            trigger: `${ADD_SHEET}[open] button[type="submit"]`,
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Back on the open card: both documents listed",
            trigger: `${DOCS} .o_sc_injury_doc_list`,
            run() {
                const names = [...document.querySelectorAll(`${DOCS} .o_sc_doc_row .o_sc_row_title`)].map(
                    (node) => node.textContent.trim()
                );
                for (const name of ["Synthetic small.pdf", "Synthetic a.pdf", "Synthetic b.pdf"]) {
                    assert(names.includes(name), `${name} missing: ${names.join(",")}`);
                }
            },
        },
        {
            content: "Re-file one: its pencil",
            trigger: `${DOCS} .o_sc_injury_doc button[data-sc-action="documents.edit"]`,
            run: "click",
        },
        {
            content: "Rename it and leave the field",
            trigger: `${DOCS} .o_sc_injury_doc[data-sc-edit-open] .o_sc_autosave[data-sc-field="name"] input`,
            run() {
                window.__sc1616NoReload = "1";
                typeAndLeave(this.anchor, "Synthetic X-ray report");
            },
        },
        {
            content: "Its row follows (read fragment) — no reload",
            trigger: ".o_sc_app",
            async run() {
                await waitFor(
                    () =>
                        [...document.querySelectorAll(`${DOCS} .o_sc_doc_row .o_sc_row_title`)].some(
                            (node) => node.textContent.trim() === "Synthetic X-ray report"
                        ),
                    "row renamed"
                );
                assert(window.__sc1616NoReload === "1", "the page reloaded");
            },
        },
    ],
});
