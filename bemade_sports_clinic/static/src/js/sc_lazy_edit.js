/*
 * bemade_portal_kit shim — task 5370 (P4b): the lazy edit views moved to
 * the kit (@bemade_portal_kit/js/pk_lazy_edit, interaction key
 * « bemade_portal_kit.pk_lazy_edit »). This one-release alias keeps the old
 * module path and export name working for code outside this addon. It only
 * re-exports: the interaction is registered once, by the kit module. It
 * goes in the next phase.
 */
export { PkLazyEdit as ScLazyEdit } from "@bemade_portal_kit/js/pk_lazy_edit";
