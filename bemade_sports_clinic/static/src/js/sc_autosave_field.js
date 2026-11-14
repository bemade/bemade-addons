/*
 * Task 5382 (kit P4c3): the autosave field is the kit's
 * (bemade_portal_kit.pk_autosave_field, @bemade_portal_kit/js/pk_autosave_field).
 *
 * One-release alias: the clinic registers the kit's class under its former
 * component key too, so a page rendered before the upgrade (a cached
 * <owl-component name="…sc_autosave_field">) or a caller that was missed
 * still mounts the field. To be deleted in the next kit phase (P3c2, #5345).
 */
import { registry } from "@web/core/registry";
import { PkAutosaveField } from "@bemade_portal_kit/js/pk_autosave_field";

registry.category("public_components").add("bemade_sports_clinic.sc_autosave_field", PkAutosaveField);
