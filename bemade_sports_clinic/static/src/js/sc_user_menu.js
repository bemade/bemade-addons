/*
 * bemade_portal_kit shim — remove in the next kit phase.
 *
 * Task 5197 (P2): sc_user_menu.js moved to the portal kit as
 * @bemade_portal_kit/js/pk_user_menu. This one-release alias keeps the old module
 * path (and its old export names) for code not yet re-pointed. Pure
 * re-export: no code, no listeners (the kit module runs once).
 */
export { close, closeAll, open } from "@bemade_portal_kit/js/pk_user_menu";
