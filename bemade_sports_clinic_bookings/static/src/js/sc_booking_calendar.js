/*
 * Task 1737 — the calendar's booking details (bemade_sports_clinic's shared
 * sc_calendar component) get the booking's « Cancel booking » / « Edit »
 * links when the feed carries them (sc_cancel_url / sc_edit_url: the
 * booking's staff user or a clinic admin, upcoming bookings only — decided
 * server-side). Both open the shell pages /my/bookings/<id>/cancel|edit.
 * The labels come from _t here: the extension's static text would be
 * translated in the PARENT template's module (bemade_sports_clinic).
 */
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { ScCalendar } from "@bemade_sports_clinic/js/sc_calendar";

patch(ScCalendar.prototype, {
    get scBookingCancelLabel() {
        return _t("Cancel booking");
    },

    get scBookingEditLabel() {
        return _t("Edit");
    },

    select(event) {
        super.select(event);
        const props = event.extendedProps || {};
        if (this.state.selected) {
            this.state.selected.editUrl = props.sc_edit_url || null;
            this.state.selected.cancelUrl = props.sc_cancel_url || null;
        }
    },
});
