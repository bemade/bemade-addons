/*
 * Task 1616 — the injury card as the injury's page (inert outside .o_sc_app):
 *
 * - button[data-sc-injury-done] (« Done » at the bottom of an open card):
 *   closes the card's open edit groups (Details / Notes / a document) and
 *   the card itself; the read fragments refresh at once (task 1611);
 * - form[data-sc-doc-upload] (the document picker — the injury card's
 *   « Add documents » sheet AND the player Documents tab, one template:
 *   bemade_sports_clinic.sc_document_upload_form): several files at once —
 *   the chosen files are listed with their size and a « × » each; choosing /
 *   dropping again ADDS to the list (review fixes 2026-10-18; duplicates
 *   ignored), a file over the limit (data-sc-max-bytes) is flagged and
 *   blocks the upload (the server refuses it too: all or nothing); on a
 *   laptop the drop zone ([data-sc-dropzone]) takes dropped files. Review
 *   fixes 2026-10-18 b: each file's row has its own name / category /
 *   description (a clone of [data-sc-file-proto]), pre-filled from the
 *   shared « Category » / « Description » when the file is added; the rows
 *   post as parallel lists (doc_file / doc_name / doc_category /
 *   doc_description) in the input's file order. Round 2 (1018c): the
 *   shared fields ([data-sc-doc-shared-group]) show only while no file is
 *   listed; hidden from the first row on, shown again when it is emptied.
 */
import { _t } from "@web/core/l10n/translation";

function inShell(node) {
    return Boolean(node && node.closest && node.closest(".o_sc_app"));
}

// ---------------------------------------------------------------- « Done »
document.addEventListener("click", (ev) => {
    const done = ev.target.closest && ev.target.closest("[data-sc-injury-done]");
    if (!done || !inShell(done)) {
        return;
    }
    const card = done.closest("details.o_sc_injury_item");
    if (!card) {
        return;
    }
    ev.preventDefault();
    // Each open edit group closes through its own « Done » (sc_app_ui.js).
    for (const button of card.querySelectorAll("[data-sc-edit-open] [data-sc-edit-done]")) {
        button.click();
    }
    if (card.contains(document.activeElement)) {
        document.activeElement.blur();
    }
    card.open = false;
    document.dispatchEvent(new CustomEvent("sc:refresh-now"));
    card.scrollIntoView({ block: "nearest" });
});

// ------------------------------------- status-only fields (review 2026-10-18)
// « Date prévue de résolution » until the injury is resolved, « Date de
// résolution » once it is: a status save (the stage island, its undo, the
// quick « Résoudre ») flips their holders ([data-sc-stage-of]) in place.
document.addEventListener("sc:saved", (ev) => {
    const detail = ev.detail || {};
    if (detail.model !== "sports.patient.injury" || detail.field !== "stage" || !detail.result) {
        return;
    }
    const result = detail.result;
    const stage = result.also && result.also.stage ? result.also.stage.value : result.value;
    if (!stage) {
        return;
    }
    for (const holder of document.querySelectorAll(`.o_sc_app [data-sc-stage-of="${detail.recordId}"]`)) {
        const show = holder.dataset.scStageShow;
        const hide = holder.dataset.scStageHide;
        holder.hidden = show ? stage !== show : hide ? stage === hide : holder.hidden;
    }
});

// ------------------------------------------------------ « Add documents »
function formatSize(bytes) {
    if (bytes >= 1024 * 1024) {
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }
    return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

// Review fixes 2026-10-18 (#1616): choosing files again (or dropping more)
// ADDS them to the selection instead of replacing it. The form keeps its own
// list (source of truth) and rebuilds the input's FileList from it
// (DataTransfer), so « Upload » posts every chosen file in one request, as
// before. The same file twice (name + size + last modified) is ignored; each
// row has a « × » to drop that file.
const selections = new WeakMap();
// Review fixes 2026-10-18 b: each chosen file's own values (File → values).
const fileValues = new WeakMap();

function fileKey(file) {
    return `${file.name}\u0000${file.size}\u0000${file.lastModified}`;
}

function selection(form) {
    if (!selections.has(form)) {
        selections.set(form, []);
    }
    return selections.get(form);
}

/** Write the form's list back into its file input (when the browser can). */
function syncInput(form) {
    const input = form.querySelector('input[type="file"]');
    if (!input || typeof DataTransfer === "undefined") {
        return;
    }
    try {
        const transfer = new DataTransfer();
        for (const file of selection(form)) {
            transfer.items.add(file);
        }
        input.files = transfer.files;
    } catch {
        // No constructible DataTransfer: the input keeps the last choice.
    }
}

/** The shared « Category » / « Description » values right now. */
function sharedValues(form) {
    const category = form.querySelector('[data-sc-doc-shared="category"]');
    const description = form.querySelector('[data-sc-doc-shared="description"]');
    return {
        category: category ? category.value : "",
        description: description ? description.value : "",
    };
}

/** Add ``files`` to the form's selection (duplicates ignored). */
export function addFiles(form, files) {
    const list = selection(form);
    const known = new Set(list.map(fileKey));
    const shared = sharedValues(form);
    for (const file of files) {
        const key = fileKey(file);
        if (!known.has(key)) {
            known.add(key);
            list.push(file);
            // Pre-filled once, when the file is added: a later change of
            // the shared fields never rewrites a row.
            fileValues.set(file, { name: file.name, ...shared });
        }
    }
    syncInput(form);
    return checkFiles(form);
}

function removeFile(form, index) {
    selection(form).splice(index, 1);
    syncInput(form);
    checkFiles(form);
}

/** List the chosen files; true when every one fits under the limit. */
function checkFiles(form) {
    const input = form.querySelector('input[type="file"]');
    const list = form.querySelector("[data-sc-file-list]");
    const error = form.querySelector("[data-sc-file-error]");
    const max = parseInt(form.dataset.scMaxBytes || "0", 10);
    const files = selections.has(form) ? selection(form) : [...(input?.files || [])];
    let ok = true;
    if (list) {
        list.replaceChildren(
            ...files.map((file, index) => {
                const item = document.createElement("li");
                const tooLarge = max && file.size > max;
                ok = ok && !tooLarge;
                item.className = tooLarge ? "o_sc_file o_sc_file_too_large" : "o_sc_file";
                item.dataset.scFileTooLarge = tooLarge ? "1" : "0";
                item.dataset.scFileIndex = String(index);
                const name = document.createElement("span");
                name.className = "o_sc_file_name";
                name.textContent = file.name;
                const size = document.createElement("span");
                size.className = "o_sc_file_size";
                size.textContent = tooLarge
                    ? _t("%(size)s — over 10 MB", { size: formatSize(file.size) })
                    : formatSize(file.size);
                const remove = document.createElement("button");
                remove.type = "button";
                remove.className = "o_sc_file_remove";
                remove.dataset.scFileRemove = String(index);
                const label = _t("Remove %(file)s", { file: file.name });
                remove.setAttribute("aria-label", label);
                remove.title = label;
                remove.textContent = "×";
                const head = document.createElement("div");
                head.className = "o_sc_file_head";
                head.append(name, size, remove);
                item.append(head);
                const row = fileRow(form, file);
                if (row) {
                    item.append(row);
                }
                return item;
            })
        );
        list.hidden = !files.length;
    } else {
        ok = !files.some((file) => max && file.size > max);
    }
    if (error) {
        error.hidden = ok;
    }
    // Review fixes 2026-10-18 (1018c): the shared « Category » /
    // « Description » only while the list is empty (they pre-fill each file
    // added); once a file is listed each row carries its own values.
    const shared = form.querySelector("[data-sc-doc-shared-group]");
    if (shared) {
        // Owner 2026-10-18: never shown (hidden defaults only).
        shared.hidden = true;
    }
    const text = form.querySelector(".o_sc_dropzone_text");
    if (text) {
        text.dataset.scOriginal = text.dataset.scOriginal || text.textContent;
        text.textContent = files.length
            ? _t("%(count)s file(s) chosen", { count: files.length })
            : text.dataset.scOriginal;
    }
    return ok;
}

/** A file's own fields (a clone of the form's row prototype). */
function fileRow(form, file) {
    const proto = form.querySelector("[data-sc-file-proto]");
    if (!proto) {
        return null;
    }
    if (!fileValues.has(file)) {
        fileValues.set(file, { name: file.name, ...sharedValues(form) });
    }
    const values = fileValues.get(file);
    const row = proto.cloneNode(true);
    row.hidden = false;
    delete row.dataset.scFileProto;
    row.dataset.scFileRow = "1";
    for (const field of row.querySelectorAll("[name]")) {
        field.disabled = false;
    }
    row.querySelector('[name="doc_file"]').value = file.name;
    const bind = (name, key) => {
        const field = row.querySelector(`[name="${name}"]`);
        if (!field) {
            return;
        }
        if (field.tagName === "SELECT" && ![...field.options].some((o) => o.value === values[key])) {
            values[key] = field.value;
        }
        field.value = values[key] || "";
        field.addEventListener("input", () => {
            values[key] = field.value;
        });
        field.addEventListener("change", () => {
            values[key] = field.value;
        });
    };
    bind("doc_name", "name");
    bind("doc_category", "category");
    bind("doc_description", "description");
    return row;
}

function uploadForm(node) {
    const form = node && node.closest && node.closest("form[data-sc-doc-upload]");
    return form && inShell(form) ? form : null;
}

document.addEventListener("change", (ev) => {
    const form = uploadForm(ev.target);
    if (form && ev.target.matches('input[type="file"]')) {
        addFiles(form, [...(ev.target.files || [])]);
    }
});

document.addEventListener("click", (ev) => {
    const remove = ev.target.closest && ev.target.closest("[data-sc-file-remove]");
    const form = remove && uploadForm(remove);
    if (!form) {
        return;
    }
    ev.preventDefault();
    removeFile(form, parseInt(remove.dataset.scFileRemove, 10));
});

// A sheet reopened after « Cancel » / a reset form starts empty again.
document.addEventListener("reset", (ev) => {
    const form = uploadForm(ev.target);
    if (form) {
        selections.delete(form);
        setTimeout(() => checkFiles(form), 0);
    }
});

document.addEventListener(
    "submit",
    (ev) => {
        const form = uploadForm(ev.target);
        if (form && !checkFiles(form)) {
            ev.preventDefault();
            ev.stopPropagation();
        }
    },
    true
);

// Drop zone (laptop): dropped files become the input's files.
for (const type of ["dragenter", "dragover"]) {
    document.addEventListener(type, (ev) => {
        const zone = ev.target.closest && ev.target.closest("[data-sc-dropzone]");
        if (zone && inShell(zone)) {
            ev.preventDefault();
            zone.classList.add("o_sc_dropzone_over");
        }
    });
}
document.addEventListener("dragleave", (ev) => {
    const zone = ev.target.closest && ev.target.closest("[data-sc-dropzone]");
    if (zone && !zone.contains(ev.relatedTarget)) {
        zone.classList.remove("o_sc_dropzone_over");
    }
});
document.addEventListener("drop", (ev) => {
    const zone = ev.target.closest && ev.target.closest("[data-sc-dropzone]");
    if (!zone || !inShell(zone)) {
        return;
    }
    ev.preventDefault();
    zone.classList.remove("o_sc_dropzone_over");
    const form = uploadForm(zone);
    if (form && ev.dataTransfer && ev.dataTransfer.files.length) {
        // Review fixes 2026-10-18: dropped files are ADDED to the selection.
        addFiles(form, [...ev.dataTransfer.files]);
    }
});
