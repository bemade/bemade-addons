/*
 * bemade_portal_kit shim — remove in the next kit phase.
 *
 * Task 5197 (P2): sc_list_header.js moved to the portal kit as
 * @bemade_portal_kit/js/pk_list_header. This one-release alias keeps the old module
 * path (and its old export names) for code not yet re-pointed. Pure
 * re-export: no code, no listeners (the kit module runs once).
 */
export { resetAddPanel } from "@bemade_portal_kit/js/pk_list_header";
