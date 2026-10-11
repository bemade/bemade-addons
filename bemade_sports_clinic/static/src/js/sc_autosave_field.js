/*
 * Task 1542 (epic #1535) — sc_autosave_field, the addon's first OWL public
 * component. Mounted from QWeb with
 *   <owl-component name="bemade_sports_clinic.sc_autosave_field" props="{...}"/>
 * (core PublicComponentInteraction, like portal.signature_form).
 *
 * Two modes:
 *
 * - « draft »: the value stays a LOCAL draft on the device while typing
 *   (sc_draft_store, per db + user + record key). It comes back after
 *   leaving the page or losing signal (« Brouillon restauré »), and is
 *   dropped once the server holds the same value (the enclosing form was
 *   published), on « Jeter le brouillon », on logout, and — task 1539 — when
 *   a page carrying data-sc-draft-clear for its key prefix loads (the
 *   « created » / « added » landing of a NEW injury or note). The field is a
 *   real form field (props.name): the enclosing form posts as before.
 *
 * - « server »: POST /my/app/save/<model>/<id> ({field, value, write_date}).
 *   Task 1539 (owner decision 2026-09-28): saved when the user LEAVES the
 *   field (blur / change), never while typing — one note-history row and
 *   one chatter line per field actually changed. Visible state
 *   (enregistrement / enregistré / erreur / hors ligne — en attente);
 *   offline or network failure queues the value in the draft store and
 *   replays it when back online; a 409 (THIS field changed elsewhere since
 *   it was loaded — the route compares old_value) shows the conflict banner (« Garder
 *   le mien » re-sends over the newer write_date, « Prendre le leur » takes
 *   the server value). ``instant`` fields (status, visibility: segmented
 *   buttons) save on click and offer « Annuler » in the shell toast, which
 *   re-posts the previous value through the same route.
 *
 * Input types: textarea | text | email | tel | date | select | segmented |
 * date_na (a date + « N/A » box, value "na" or YYYY-MM-DD) | tags (CSV of the
 * chosen option keys: removable chips + a search box suggesting a few options).
 */
import { Component, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { scFetch } from "@bemade_sports_clinic/js/sc_fetch";
import { readDraft, removeDraft, writeDraft } from "@bemade_sports_clinic/js/sc_draft_store";

const DRAFT_DEBOUNCE = 300;
// tags: suggestions shown at once (owner review 2026-10-10: never a long list).
const TAGS_MAX_MATCHES = 8;

function fold(text) {
    return String(text || "")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase();
}

function norm(value) {
    return (value === null || value === undefined || value === false ? "" : String(value)).trim();
}

function asText(value) {
    return norm(value) === "" ? "" : String(value);
}

export class ScAutosaveField extends Component {
    static template = "bemade_sports_clinic.ScAutosaveField";
    static props = {
        mode: { type: String, optional: true }, // "draft" (default) | "server"
        name: { type: String, optional: true },
        naName: { type: String, optional: true }, // date_na, draft mode
        inputType: { type: String, optional: true },
        inputId: { type: String, optional: true },
        label: { type: String, optional: true },
        hint: { type: String, optional: true },
        placeholder: { type: String, optional: true },
        value: { optional: true },
        options: { type: Array, optional: true }, // [[value, label], ...]
        required: { type: Boolean, optional: true },
        disabled: { type: Boolean, optional: true },
        instant: { type: Boolean, optional: true },
        clearable: { type: Boolean, optional: true },
        undoMessage: { type: String, optional: true },
        draftKey: { type: String, optional: true },
        // server mode
        model: { type: String, optional: true },
        recordId: { type: Number, optional: true },
        field: { type: String, optional: true },
        writeDate: { type: String, optional: true },
        "*": true,
    };

    setup() {
        this.inputRef = useRef("input");
        this.state = useState({
            value: asText(this.props.value),
            status: "idle", // idle | dirty | draft | saving | saved | queued | error | conflict
            restored: false,
            conflict: null,
            savedAt: "",
            message: "",
            error: "",
            query: "", // tags: the search box
        });
        this.writeDate = this.props.writeDate || "";
        // The field value the server last held (sent as old_value: a record
        // written since — e.g. a sibling field saved — is not a conflict
        // while THIS field is unchanged there).
        this.lastSaved = asText(this.props.value);
        this.timer = null;
        this.onOnline = () => {
            if (this.state.status === "queued") {
                this.save();
            }
        };
        onMounted(() => this.restore());
        onWillUnmount(() => {
            clearTimeout(this.timer);
            window.removeEventListener("online", this.onOnline);
        });
        if (this.isServer) {
            window.addEventListener("online", this.onOnline);
        }
    }

    get isServer() {
        return this.props.mode === "server";
    }

    get type() {
        return this.props.inputType || "text";
    }

    get isNa() {
        return this.state.value === "na";
    }

    get dateValue() {
        return this.isNa ? "" : this.state.value;
    }

    get key() {
        if (this.props.draftKey) {
            return this.props.draftKey;
        }
        return `${this.props.model}.${this.props.recordId}.${this.props.field}`;
    }

    get statusLabel() {
        switch (this.state.status) {
            case "draft":
                return _t("Draft kept on this device");
            case "saving":
                return _t("Saving…");
            case "saved":
                return this.state.savedAt ? _t("Saved · %s", this.state.savedAt) : _t("Saved");
            case "queued":
                return _t("Offline — pending");
            case "error":
                return _t("Error — not saved");
            case "conflict":
                return _t("Changed elsewhere");
            default:
                return "";
        }
    }

    get conflictText() {
        const by = this.state.conflict && this.state.conflict.by;
        return by
            ? _t("%s changed this field while you were typing.", by)
            : _t("This field was changed elsewhere while you were typing.");
    }

    get naLabel() {
        return _t("N/A");
    }

    get noMatchLabel() {
        return _t("No match");
    }

    removeLabel(label) {
        return _t("Remove %s", label);
    }

    // ------------------------------------------------------------ restore
    restore() {
        const draft = readDraft(this.key);
        if (!draft) {
            return;
        }
        if (this.isServer) {
            // A queued (unsent) value: show it and send it again.
            this.state.value = draft.value;
            this.writeDate = draft.writeDate || this.writeDate;
            this.state.status = "queued";
            if (navigator.onLine !== false) {
                this.save();
            }
            return;
        }
        if (norm(draft.value) === norm(this.props.value)) {
            // The server already holds it (published): the draft is done.
            removeDraft(this.key);
            return;
        }
        this.state.value = draft.value;
        this.state.restored = true;
        this.state.status = "draft";
        const details = this.inputRef.el && this.inputRef.el.closest("details");
        if (details) {
            details.open = true;
        }
    }

    discardDraft() {
        removeDraft(this.key);
        this.state.value = asText(this.props.value);
        this.state.restored = false;
        this.state.status = "idle";
    }

    // -------------------------------------------------------------- input
    onInput() {
        clearTimeout(this.timer);
        this.state.status = "dirty";
        if (!this.isServer) {
            this.timer = setTimeout(() => this.keepDraft(), DRAFT_DEBOUNCE);
        }
    }

    /** blur / change: the user left the field (or picked a value). */
    commit() {
        if (this.state.status !== "dirty") {
            return;
        }
        clearTimeout(this.timer);
        if (this.isServer) {
            this.save();
        } else {
            this.keepDraft();
        }
    }

    /** « Effacer »: an explicit clear, saved (or drafted) at once. */
    clear() {
        this.state.value = "";
        this.state.status = "dirty";
        this.commit();
    }

    onChange() {
        this.state.status = "dirty";
        this.commit();
    }

    onNaToggle(ev) {
        if (ev.target.checked) {
            this.state.value = "na";
        } else {
            this.state.value = "";
            // Nothing to save until a date is picked (the model refuses a
            // blank date without « N/A »).
            this.state.status = "idle";
            return;
        }
        this.onChange();
    }

    // --------------------------------------------------------------- tags
    get checkedKeys() {
        return (this.state.value || "").split(",").map((key) => key.trim()).filter(Boolean);
    }

    isChecked(key) {
        return this.checkedKeys.includes(String(key));
    }

    get chosenOptions() {
        const keys = this.checkedKeys;
        return (this.props.options || []).filter((opt) => keys.includes(String(opt[0])));
    }

    get tagMatches() {
        const query = fold(this.state.query).trim();
        if (!query) {
            return [];
        }
        const words = query.split(/\s+/);
        return (this.props.options || [])
            .filter((opt) => !this.isChecked(opt[0]))
            .filter((opt) => words.every((word) => fold(opt[1]).includes(word)))
            .slice(0, TAGS_MAX_MATCHES);
    }

    addTag(key) {
        this.state.query = "";
        this.onCheck(key, true);
        if (this.inputRef.el) {
            this.inputRef.el.focus();
        }
    }

    onTagKeydown(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            const first = this.tagMatches[0];
            if (first) {
                this.addTag(first[0]);
            }
        } else if (ev.key === "Escape") {
            this.state.query = "";
        }
    }

    onCheck(key, checked) {
        const keys = new Set(this.checkedKeys);
        if (checked) {
            keys.add(String(key));
        } else {
            keys.delete(String(key));
        }
        this.onPick([...keys].sort((a, b) => Number(a) - Number(b)).join(","));
    }

    onPick(value) {
        if (this.props.disabled || String(value) === this.state.value) {
            return;
        }
        const previous = this.state.value;
        this.state.value = String(value);
        this.state.status = "dirty";
        if (this.isServer) {
            this.save().then((ok) => {
                if (ok && this.props.instant) {
                    this.offerUndo(previous);
                }
            });
        } else {
            this.keepDraft();
        }
    }

    offerUndo(previous) {
        document.dispatchEvent(
            new CustomEvent("sc:toast", {
                detail: {
                    message: this.props.undoMessage || _t("Change saved"),
                    actionLabel: _t("Undo"),
                    action: () => {
                        this.state.value = previous;
                        this.save();
                    },
                },
            })
        );
    }

    keepDraft() {
        if (norm(this.state.value) === norm(this.props.value)) {
            removeDraft(this.key);
            this.state.status = "idle";
            return;
        }
        this.state.status = writeDraft(this.key, { value: this.state.value }) ? "draft" : "idle";
    }

    // --------------------------------------------------------------- save
    get saveUrl() {
        return `/my/app/save/${encodeURIComponent(this.props.model)}/${this.props.recordId}`;
    }

    queue() {
        writeDraft(this.key, { value: this.state.value, writeDate: this.writeDate });
        this.state.status = "queued";
    }

    /** @returns {Promise<boolean>} saved */
    async save() {
        clearTimeout(this.timer);
        if (navigator.onLine === false) {
            this.queue();
            return false;
        }
        this.state.status = "saving";
        this.state.error = "";
        try {
            const result = await scFetch(this.saveUrl, {
                method: "POST",
                data: {
                    field: this.props.field,
                    value: this.state.value,
                    write_date: this.writeDate,
                    old_value: this.lastSaved,
                },
                toast: false,
            });
            this.writeDate = result.write_date;
            if (result.value !== undefined && this.type !== "textarea") {
                this.state.value = asText(result.value);
            }
            this.lastSaved = result.value !== undefined ? asText(result.value) : this.state.value;
            this.state.message = result.message || "";
            removeDraft(this.key);
            const now = new Date();
            this.state.savedAt = `${now.getHours()}:${String(now.getMinutes()).padStart(2, "0")}`;
            this.state.status = "saved";
            this.state.conflict = null;
            // Lets the page reflect a save elsewhere (e.g. the player's
            // status pill, owner review 2026-10-10).
            document.dispatchEvent(
                new CustomEvent("sc:saved", {
                    detail: {
                        model: this.props.model,
                        recordId: this.props.recordId,
                        field: this.props.field,
                        result,
                    },
                })
            );
            return true;
        } catch (error) {
            if (error.status === 409 && error.payload) {
                this.state.conflict = error.payload;
                this.state.status = "conflict";
            } else if (error.status === 0) {
                this.queue();
            } else {
                this.state.status = "error";
                this.state.error = (error.payload && error.payload.message) || "";
            }
            return false;
        }
    }

    keepMine() {
        this.writeDate = this.state.conflict.current_write_date;
        this.lastSaved = asText(this.state.conflict.current_value);
        this.state.conflict = null;
        this.save();
    }

    takeTheirs() {
        const conflict = this.state.conflict;
        this.state.value = asText(conflict.current_value);
        this.writeDate = conflict.current_write_date;
        this.lastSaved = this.state.value;
        this.state.conflict = null;
        removeDraft(this.key);
        this.state.status = "saved";
    }
}

registry.category("public_components").add("bemade_sports_clinic.sc_autosave_field", ScAutosaveField);
