/*
 * Task 1542 (epic #1535) — sc_autosave_field, the addon's first OWL public
 * component. Mounted from QWeb with
 *   <owl-component name="bemade_sports_clinic.sc_autosave_field" props="{...}"/>
 * (core PublicComponentInteraction, like portal.signature_form).
 *
 * Two modes:
 *
 * - « draft »: the text stays a LOCAL draft on the device while typing
 *   (sc_draft_store, per db + user + record key). It comes back after
 *   leaving the page or losing signal (« Brouillon restauré »), and is
 *   dropped once the server holds the same value (the enclosing form was
 *   published), on « Jeter le brouillon », and on logout. The field is a
 *   real form field (props.name): the enclosing form posts as before.
 *   Used live by the team announcement.
 *
 * - « server »: debounced save on input and on blur through
 *   POST /my/app/save/<model>/<id> ({field, value, write_date}); visible
 *   state (enregistrement / enregistré / erreur / hors ligne — en attente);
 *   offline or network failure queues the value in the draft store and
 *   replays it when back online; a 409 shows the conflict banner (« Garder
 *   le mien » re-sends over the newer write_date, « Prendre le leur » takes
 *   the server value). NOT used live until P2 (the registry is empty).
 */
import { Component, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { scFetch } from "@bemade_sports_clinic/js/sc_fetch";
import { readDraft, removeDraft, writeDraft } from "@bemade_sports_clinic/js/sc_draft_store";

const DRAFT_DEBOUNCE = 300;
const SAVE_DEBOUNCE = 800;

function norm(value) {
    return (value === null || value === undefined || value === false ? "" : String(value)).trim();
}

export class ScAutosaveField extends Component {
    static template = "bemade_sports_clinic.ScAutosaveField";
    static props = {
        mode: { type: String, optional: true }, // "draft" (default) | "server"
        name: { type: String, optional: true },
        inputType: { type: String, optional: true }, // textarea | text | date
        inputId: { type: String, optional: true },
        label: { type: String, optional: true },
        placeholder: { type: String, optional: true },
        value: { optional: true },
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
            value: norm(this.props.value) === "" ? "" : String(this.props.value),
            status: "idle", // idle | dirty | draft | saving | saved | queued | error | conflict
            restored: false,
            conflict: null,
            savedAt: "",
        });
        this.writeDate = this.props.writeDate || "";
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
        this.state.value = norm(this.props.value) === "" ? "" : String(this.props.value);
        this.state.restored = false;
        this.state.status = "idle";
    }

    // -------------------------------------------------------------- input
    onInput() {
        clearTimeout(this.timer);
        this.state.status = "dirty";
        if (this.isServer) {
            this.timer = setTimeout(() => this.save(), SAVE_DEBOUNCE);
        } else {
            this.timer = setTimeout(() => this.keepDraft(), DRAFT_DEBOUNCE);
        }
    }

    onBlur() {
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

    async save() {
        clearTimeout(this.timer);
        if (navigator.onLine === false) {
            this.queue();
            return;
        }
        this.state.status = "saving";
        try {
            const result = await scFetch(this.saveUrl, {
                method: "POST",
                data: { field: this.props.field, value: this.state.value, write_date: this.writeDate },
                toast: false,
            });
            this.writeDate = result.write_date;
            removeDraft(this.key);
            const now = new Date();
            this.state.savedAt = `${now.getHours()}:${String(now.getMinutes()).padStart(2, "0")}`;
            this.state.status = "saved";
            this.state.conflict = null;
        } catch (error) {
            if (error.status === 409 && error.payload) {
                this.state.conflict = error.payload;
                this.state.status = "conflict";
            } else if (error.status === 0) {
                this.queue();
            } else {
                this.state.status = "error";
            }
        }
    }

    keepMine() {
        this.writeDate = this.state.conflict.current_write_date;
        this.state.conflict = null;
        this.save();
    }

    takeTheirs() {
        const conflict = this.state.conflict;
        this.state.value = norm(conflict.current_value) === "" ? "" : String(conflict.current_value);
        this.writeDate = conflict.current_write_date;
        this.state.conflict = null;
        removeDraft(this.key);
        this.state.status = "saved";
    }
}

registry.category("public_components").add("bemade_sports_clinic.sc_autosave_field", ScAutosaveField);
