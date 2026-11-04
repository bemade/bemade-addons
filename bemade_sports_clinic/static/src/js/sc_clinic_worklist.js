/*
 * Task 1540 (epic #1535, P3) — sc_clinic_worklist, the LIVE clinic waiting
 * list of the app shell. Mounted from QWeb (sc_app_clinic) with
 *   <owl-component name="bemade_sports_clinic.sc_clinic_worklist" props="{...}"/>
 * whose server-rendered content (the no-JS list) is replaced on mount.
 *
 * - First paint from props.data (no fetch); then a poll of props.dataUrl
 *   every props.pollSeconds (20 s) while the page is visible, through
 *   scFetch (toast: false). The poll is PAUSED while a row is dragged,
 *   while an action is in flight and while a sheet is open (resolve,
 *   add, kiosk…); an error backs off (x2, up to 5 min) and a success resets
 *   the interval. Rows are replaced only when the server's version hash
 *   changed.
 * - Actions (status, confirm, remove, reorder by drag or up / down) apply
 *   at once (optimistic) and POST to the JSON twins of the attendance routes
 *   (props.actionUrl + state | confirm | remove | reorder; CSRF by scFetch).
 *   The answer carries the CURRENT worklist, which replaces the local one
 *   (reconcile); a failure rolls back (to the server's list when the answer
 *   carries it) and shows a toast.
 * - « Remove » asks for a second tap (the row is deleted, not archived).
 * - An unregistered kiosk sign-in (#1418) has no status buttons: « Resolve »
 *   opens the page's resolve sheet, whose three forms (link / create /
 *   remove, today's PRG routes) get this row's id from the listener below.
 */
import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { scFetch } from "@bemade_sports_clinic/js/sc_fetch";

const MAX_BACKOFF = 300000;
const ARM_MS = 4000;

function clone(data) {
    return { ...data, rows: data.rows.map((row) => ({ ...row })) };
}

function toast(message) {
    document.dispatchEvent(new CustomEvent("sc:toast", { detail: { message } }));
}

export class ScClinicWorklist extends Component {
    static template = "bemade_sports_clinic.ScClinicWorklist";
    static props = {
        clinicId: Number,
        dataUrl: String,
        actionUrl: String,
        selectedPatientId: { type: Number, optional: true },
        data: Object,
        pollSeconds: { type: Number, optional: true },
        "*": true,
    };

    setup() {
        this.state = useState({
            data: this.props.data,
            status: "live", // live | offline | error
            pending: 0,
            armed: 0, // row id whose « Remove » waits for its second tap
            dragId: 0,
            overId: 0,
        });
        this.base = (this.props.pollSeconds || 20) * 1000;
        this.interval = this.base;
        this.timer = null;
        this.armTimer = null;
        this.onVisibility = () => {
            if (document.visibilityState === "visible") {
                this.schedule(0);
            }
        };
        onMounted(() => {
            document.addEventListener("visibilitychange", this.onVisibility);
            this.schedule();
        });
        onWillUnmount(() => {
            clearTimeout(this.timer);
            clearTimeout(this.armTimer);
            document.removeEventListener("visibilitychange", this.onVisibility);
        });
    }

    // ------------------------------------------------------------ getters
    get rows() {
        return this.state.data.rows || [];
    }

    get liveLabel() {
        if (this.state.status === "offline") {
            return _t("Offline");
        }
        if (this.state.status === "error") {
            return _t("Reconnecting…");
        }
        return this.paused ? _t("Paused") : _t("Live");
    }

    get waitingLabel() {
        const count = this.state.data.waiting || 0;
        return count === 1 ? _t("1 waiting") : _t("%s waiting", count);
    }

    get paused() {
        return Boolean(
            this.state.dragId || this.state.pending || document.querySelector("dialog.o_sc_sheet[open]")
        );
    }

    subtitle(row) {
        if (row.unregistered) {
            return row.dob ? _t("Unregistered sign-in · %s", row.dob) : _t("Unregistered sign-in");
        }
        if (row.state === "seen" && row.seenAt) {
            return _t("Seen %s", row.seenAt);
        }
        if (row.arrivedAt && row.state !== "expected") {
            return _t("Arrived %s", row.arrivedAt);
        }
        return _t("Expected");
    }

    rowClass(row) {
        const classes = ["o_sc_wl_row"];
        if (row.state === "seen") {
            classes.push("o_sc_wl_row_seen");
        }
        if (row.unregistered) {
            classes.push("o_sc_wl_row_unregistered");
        }
        if (row.patientId && row.patientId === this.props.selectedPatientId) {
            classes.push("o_sc_wl_row_selected");
        }
        if (row.id === this.state.dragId) {
            classes.push("o_sc_wl_row_dragging");
        }
        if (row.id === this.state.overId && row.id !== this.state.dragId) {
            classes.push("o_sc_wl_row_over");
        }
        return classes.join(" ");
    }

    // --------------------------------------------------------------- poll
    schedule(delay = this.interval) {
        clearTimeout(this.timer);
        this.timer = setTimeout(() => this.poll(), delay);
    }

    async poll() {
        if (document.visibilityState === "hidden") {
            return; // resumed by visibilitychange
        }
        if (this.paused) {
            this.schedule(this.base);
            return;
        }
        try {
            const data = await scFetch(this.props.dataUrl, { toast: false });
            if (!this.paused) {
                this.apply(data);
            }
            this.interval = this.base;
            this.state.status = "live";
        } catch (error) {
            this.interval = Math.min(this.interval * 2, MAX_BACKOFF);
            this.state.status = error.status === 0 ? "offline" : "error";
        }
        this.schedule();
    }

    apply(data) {
        if (data && data.rows && data.version !== this.state.data.version) {
            this.state.data = data;
        }
    }

    // ------------------------------------------------------------ actions
    async act(action, fields, change) {
        const snapshot = this.state.data;
        if (change) {
            const next = clone(snapshot);
            change(next);
            this.state.data = next;
        }
        this.state.pending++;
        try {
            const result = await scFetch(this.props.actionUrl + action, {
                method: "POST",
                data: fields,
                toast: false,
            });
            if (result && result.data) {
                this.state.data = result.data;
            }
            this.state.status = "live";
            return true;
        } catch (error) {
            const payload = error.payload || {};
            this.state.data = payload.data && payload.data.rows ? payload.data : snapshot;
            toast(
                payload.message ||
                    (error.status === 0
                        ? _t("No connection. Try again when you are back online.")
                        : _t("The change could not be saved."))
            );
            return false;
        } finally {
            this.state.pending--;
        }
    }

    setState(row, value) {
        if (row.unregistered || row.state === value) {
            return;
        }
        this.act("state", { attendance_id: row.id, state: value }, (data) => {
            const target = data.rows.find((r) => r.id === row.id);
            if (target) {
                target.state = value;
            }
        });
    }

    confirm(row) {
        this.act("confirm", { attendance_id: row.id }, (data) => {
            const target = data.rows.find((r) => r.id === row.id);
            if (target) {
                target.toConfirm = false;
            }
        });
    }

    remove(row) {
        if (this.state.armed !== row.id) {
            this.state.armed = row.id;
            clearTimeout(this.armTimer);
            this.armTimer = setTimeout(() => {
                this.state.armed = 0;
            }, ARM_MS);
            return;
        }
        this.state.armed = 0;
        this.act("remove", { attendance_id: row.id }, (data) => {
            data.rows = data.rows.filter((r) => r.id !== row.id);
            data.count = data.rows.length;
        });
    }

    move(row, direction) {
        this.act("reorder", { attendance_id: row.id, direction }, (data) => {
            const index = data.rows.findIndex((r) => r.id === row.id);
            const other = direction === "up" ? index - 1 : index + 1;
            if (index < 0 || other < 0 || other >= data.rows.length) {
                return;
            }
            [data.rows[index], data.rows[other]] = [data.rows[other], data.rows[index]];
        });
    }

    // --------------------------------------------------------------- drag
    onDragStart(row, ev) {
        this.state.dragId = row.id;
        if (ev.dataTransfer) {
            ev.dataTransfer.effectAllowed = "move";
            ev.dataTransfer.setData("text/plain", String(row.id));
        }
    }

    onDragOver(row, ev) {
        if (!this.state.dragId) {
            return;
        }
        ev.preventDefault();
        this.state.overId = row.id;
    }

    onDragEnd() {
        this.state.dragId = 0;
        this.state.overId = 0;
    }

    onDrop(row, ev) {
        ev.preventDefault();
        const dragId = this.state.dragId;
        this.onDragEnd();
        if (!dragId || dragId === row.id) {
            return;
        }
        const ids = this.rows.map((r) => r.id).filter((id) => id !== dragId);
        ids.splice(ids.indexOf(row.id), 0, dragId);
        this.act("reorder", { order: ids.join(",") }, (data) => {
            const byId = new Map(data.rows.map((r) => [r.id, r]));
            data.rows = ids.map((id) => byId.get(id)).filter(Boolean);
        });
    }
}

registry.category("public_components").add("bemade_sports_clinic.sc_clinic_worklist", ScClinicWorklist);

// « Resolve » (#1418): point the page's resolve sheet at the clicked row.
document.addEventListener("click", (ev) => {
    const opener = ev.target.closest && ev.target.closest("[data-sc-resolve-id]");
    if (!opener || !opener.closest(".o_sc_app")) {
        return;
    }
    const sheet = document.getElementById("sc_clinic_resolve_sheet");
    if (!sheet) {
        return;
    }
    for (const form of sheet.querySelectorAll("form[data-sc-action-template]")) {
        form.action = form.dataset.scActionTemplate.replace("__ID__", opener.dataset.scResolveId);
    }
    const name = sheet.querySelector("[data-sc-resolve-name]");
    if (name) {
        name.textContent = opener.dataset.scResolveName || "";
    }
});
