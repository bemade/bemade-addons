/*
 * Task 1540 (epic #1535, P3) — sc_calendar, the app shell's ONE calendar
 * component (events, and bookings through bemade_sports_clinic_bookings).
 * Mounted from QWeb (sc_calendar template) with
 *   <owl-component name="bemade_sports_clinic.sc_calendar" props="{...}"/>
 *
 * FullCalendar comes from Odoo's own lazy bundle ``web.fullcalendar_lib``
 * (loaded once, on mount — never a raw <script src>, never on other
 * pages). Events are fetched from props.feedUrl through scFetch with the
 * visible range (start / end ISO) plus props.params (the page's filters);
 * the feed's JSON shape is unchanged. An event with a ``url`` navigates;
 * otherwise (bookings) a click shows its details under the calendar, from
 * props.detailKeys [[key, label], …] read in extendedProps.
 */
import { Component, onMounted, onWillStart, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { loadBundle } from "@web/core/assets";
import { _t } from "@web/core/l10n/translation";
import { scFetch } from "@bemade_sports_clinic/js/sc_fetch";

const PHONE = 700;

export class ScCalendar extends Component {
    static template = "bemade_sports_clinic.ScCalendar";
    static props = {
        feedUrl: String,
        params: { type: Object, optional: true },
        locale: { type: String, optional: true },
        detailKeys: { type: Array, optional: true },
        "*": true,
    };

    setup() {
        this.calRef = useRef("calendar");
        this.state = useState({ selected: null, error: false, ready: false });
        onWillStart(async () => {
            try {
                await loadBundle("web.fullcalendar_lib");
            } catch {
                this.state.error = true;
            }
        });
        onMounted(() => this.renderCalendar());
        onWillUnmount(() => this.calendar && this.calendar.destroy());
    }

    get errorLabel() {
        return _t("The calendar could not be loaded.");
    }

    fetchEvents(info, success, failure) {
        const query = new URLSearchParams({
            ...(this.props.params || {}),
            start: info.startStr,
            end: info.endStr,
        });
        scFetch(`${this.props.feedUrl}?${query}`, { toast: false })
            .then((events) => success(events || []))
            .catch((error) => {
                this.state.error = true;
                failure(error);
            });
    }

    renderCalendar() {
        const FullCalendar = window.FullCalendar;
        if (!FullCalendar || !this.calRef.el) {
            this.state.error = true;
            return;
        }
        const phone = window.innerWidth < PHONE;
        this.calendar = new FullCalendar.Calendar(this.calRef.el, {
            initialView: phone ? "listWeek" : "dayGridMonth",
            locale: this.props.locale || "en",
            height: "auto",
            firstDay: 1,
            headerToolbar: {
                left: "prev,next today",
                center: "title",
                right: phone ? "listWeek,dayGridMonth" : "dayGridMonth,timeGridWeek,listWeek",
            },
            events: (info, success, failure) => this.fetchEvents(info, success, failure),
            eventClick: (info) => {
                if (info.event.url) {
                    return; // FullCalendar follows the link
                }
                info.jsEvent.preventDefault();
                this.select(info.event);
            },
        });
        this.calendar.render();
        this.state.ready = true;
    }

    select(event) {
        const props = event.extendedProps || {};
        const fmt = { dateStyle: "medium", timeStyle: "short" };
        const lang = document.documentElement.lang || undefined;
        const when = [event.start, event.end]
            .filter(Boolean)
            .map((date) => date.toLocaleString(lang, fmt))
            .join(" – ");
        const lines = [];
        for (const [key, label] of this.props.detailKeys || []) {
            const value = props[key];
            if (value) {
                lines.push({ key, label, value: Array.isArray(value) ? value.join(", ") : String(value) });
            }
        }
        this.state.selected = { title: event.title, when, lines, cancelled: Boolean(props.cancelled) };
    }

    close() {
        this.state.selected = null;
    }
}

registry.category("public_components").add("bemade_sports_clinic.sc_calendar", ScCalendar);
