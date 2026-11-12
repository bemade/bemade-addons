/*
 * bemade_portal_kit shim — task 5370 (P4b): the form guard moved to the kit
 * (@bemade_portal_kit/js/pk_form_guard). This one-release alias keeps the
 * old module path working for code outside this addon; every importer here
 * uses the kit path. It only re-exports: the guard's listeners are the kit
 * module's, bound once. It goes in the next phase.
 */
export {
    guardBoot,
    guardClearError,
    guardFlash,
    guardForm,
    guardReason,
    guardRefresh,
    guardRefusal,
    guardShowError,
} from "@bemade_portal_kit/js/pk_form_guard";
