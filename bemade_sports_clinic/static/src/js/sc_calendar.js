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
 * props.detailKeys [[key, label], …] read in extendedProps (an optional
 * third item "tel" / "mailto" renders the value as a tap link, task 1585).
 *
 * Task 1605 (opt-in prop ``staffColors``, the events calendar only): a dot
 * before each event's title in the colour of its assigned person
 * (extendedProps.staff [{id, name, color}]) — a split circle for several,
 * grey when nobody is assigned — and a legend under the calendar of the
 * people in the visible range; tapping one reloads the page filtered on
 * them (the filter bar's ``assigned_user_id``, task 1591's URL sync), the
 * visible date and view kept in the URL hash.
 */
import { Component, onMounted, onWillStart, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { loadBundle } from "@web/core/assets";
import { _t } from "@web/core/l10n/translation";
import { scFetch } from "@bemade_sports_clinic/js/sc_fetch";
import { scContactHref } from "@bemade_sports_clinic/js/sc_contact_href";

const PHONE = 700;
const ASSIGNED = "assigned_user_id";

/** CSS background of a staff dot: one colour, or equal conic slices. */
export function staffDotBackground(colors) {
    if (colors.length === 1) {
        return colors[0];
    }
    const step = 100 / colors.length;
    const slices = colors.map(
        (color, index) => `${color} ${(index * step).toFixed(2)}% ${((index + 1) * step).toFixed(2)}%`
    );
    return `conic-gradient(${slices.join(", ")})`;
}

/** The legend: people assigned to the given events, by name (unique). */
export function staffLegend(events) {
    const byId = new Map();
    let unassigned = false;
    for (const event of events) {
        const staff = (event.extendedProps && event.extendedProps.staff) || [];
        if (!staff.length) {
            unassigned = true;
        }
        for (const person of staff) {
            if (person.color && !byId.has(person.id)) {
                byId.set(person.id, { id: person.id, name: person.name, color: person.color });
            }
        }
    }
    const people = [...byId.values()].sort((a, b) => a.name.localeCompare(b.name));
    return { people, unassigned };
}

export class ScCalendar extends Component {
    static template = "bemade_sports_clinic.ScCalendar";
    static props = {
        feedUrl: String,
        params: { type: Object, optional: true },
        locale: { type: String, optional: true },
        detailKeys: { type: Array, optional: true },
        staffColors: { type: Boolean, optional: true },
        "*": true,
    };

    setup() {
        this.calRef = useRef("calendar");
        this.state = useState({
            selected: null,
            error: false,
            ready: false,
            legend: { people: [], unassigned: false },
            legendReady: false,
        });
        this.activeStaff = new URLSearchParams(window.location.search).get(ASSIGNED) || "";
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

    get legendTitle() {
        return _t("Therapists");
    }

    get unassignedLabel() {
        return _t("Unassigned");
    }

    get showAllLabel() {
        return _t("Show all therapists");
    }

    /** Filtered on someone who has no event in the visible range. */
    get activeMissing() {
        return this.state.legendReady && Boolean(this.activeStaff) && !this.state.legend.people.some((p) => this.isActive(p));
    }

    legendLabel(person) {
        return this.isActive(person) ? this.showAllLabel : _t("Show only %s", person.name);
    }

    isActive(person) {
        return Boolean(person) && String(person.id) === this.activeStaff;
    }

    /** The visible date / view kept across the legend's reload (hash). */
    initialPosition(views) {
        const hash = new URLSearchParams(window.location.hash.slice(1));
        const position = {};
        const date = hash.get("sc_date");
        if (date && /^\d{4}-\d{2}-\d{2}$/.test(date)) {
            position.initialDate = date;
        }
        if (views.includes(hash.get("sc_view"))) {
            position.initialView = hash.get("sc_view");
        }
        return position;
    }

    mountStaffDot(info) {
        const staff = info.event.extendedProps.staff || [];
        const dot = document.createElement("span");
        dot.className = "o_sc_staff_dot";
        dot.setAttribute("role", "img");
        dot.dataset.scStaffDot = staff.map((person) => person.id).join(",") || "none";
        const names = staff.map((person) => person.name).join(", ");
        const label = names || this.unassignedLabel;
        dot.setAttribute("aria-label", label);
        dot.title = label;
        const colors = staff.map((person) => person.color).filter(Boolean);
        if (colors.length) {
            dot.style.background = staffDotBackground(colors);
        } else {
            dot.classList.add("o_sc_staff_dot_none");
        }
        // Replaces FullCalendar's own dot (month / list); else before the title.
        const fcDot = info.el.querySelector(".fc-daygrid-event-dot, .fc-list-event-dot");
        if (fcDot) {
            fcDot.before(dot);
        } else {
            const title = info.el.querySelector(".fc-event-title, .fc-list-event-title a");
            (title || info.el).prepend(dot);
        }
    }

    refreshLegend() {
        const view = this.calendar && this.calendar.view;
        if (!view) {
            return;
        }
        const inRange = this.calendar.getEvents().filter((event) => {
            const end = event.end || event.start;
            return event.start < view.activeEnd && end >= view.activeStart;
        });
        this.state.legend = staffLegend(inRange);
    }

    filterOn(person) {
        const url = new URL(window.location.href);
        if (!person || this.isActive(person)) {
            url.searchParams.delete(ASSIGNED);
        } else {
            url.searchParams.set(ASSIGNED, String(person.id));
        }
        const hash = new URLSearchParams();
        hash.set("sc_date", this.calendar.formatIso(this.calendar.getDate(), true));
        hash.set("sc_view", this.calendar.view.type);
        url.hash = hash.toString();
        window.location.assign(url.toString());
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
        const views = phone ? ["listWeek", "dayGridMonth"] : ["dayGridMonth", "timeGridWeek", "listWeek"];
        const staffOptions = this.props.staffColors
            ? {
                  eventDidMount: (info) => this.mountStaffDot(info),
                  eventsSet: () => {
                      this.state.legendReady = true;
                      this.refreshLegend();
                  },
                  datesSet: () => this.refreshLegend(),
                  ...this.initialPosition(views),
              }
            : {};
        this.calendar = new FullCalendar.Calendar(this.calRef.el, {
            initialView: phone ? "listWeek" : "dayGridMonth",
            ...staffOptions,
            locale: this.props.locale || "en",
            height: "auto",
            firstDay: 1,
            headerToolbar: {
                left: "prev,next today",
                center: "title",
                right: views.join(","),
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
        for (const [key, label, kind] of this.props.detailKeys || []) {
            const value = props[key];
            if (value) {
                const shown = Array.isArray(value) ? value.join(", ") : String(value);
                // Task 1585: a [key, label, "tel" | "mailto"] entry is a
                // tap-to-call / tap-to-email link.
                lines.push({ key, label, value: shown, href: kind ? scContactHref(kind, shown) : null });
            }
        }
        this.state.selected = { title: event.title, when, lines, cancelled: Boolean(props.cancelled) };
    }

    close() {
        this.state.selected = null;
    }
}

registry.category("public_components").add("bemade_sports_clinic.sc_calendar", ScCalendar);
