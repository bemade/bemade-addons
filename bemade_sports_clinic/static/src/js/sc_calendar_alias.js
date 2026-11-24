/*
 * Task 5200 (kit P5) — the calendar component moved to the kit
 * (@bemade_portal_kit/js/pk_calendar, key bemade_portal_kit.pk_calendar).
 * One-release alias: a page still mounting the old key (e.g. a website copy
 * of a view) gets the kit's component. Remove at the next kit phase.
 */
import { registry } from "@web/core/registry";
import { PkCalendar } from "@bemade_portal_kit/js/pk_calendar";

registry.category("public_components").add("bemade_sports_clinic.sc_calendar", PkCalendar);
