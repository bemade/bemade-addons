/*
 * bemade_portal_kit shim — task 5370 (P4b): the status pills moved to the
 * kit (@bemade_portal_kit/js/pk_status_pills). This one-release alias keeps
 * the old module path working for code outside this addon (the old module
 * exported nothing: importing it ran it). It only re-exports: the pills'
 * listeners are the kit module's, bound once. It goes in the next phase.
 */
export { PILL_SELECTOR } from "@bemade_portal_kit/js/pk_status_pills";
