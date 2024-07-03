/** @odoo-module **/

import {Many2ManyTagsField} from "@web/views/fields/many2many_tags/many2many_tags_field";
import {MrpDisplayRecord} from "@mrp_workorder/mrp_display/mrp_display_record";

MrpDisplayRecord.components = {
  ...MrpDisplayRecord.components,
  Many2ManyTagsField,
};
