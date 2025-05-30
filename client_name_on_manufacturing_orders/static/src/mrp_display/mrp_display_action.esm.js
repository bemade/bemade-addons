/** @odoo-module **/

import {MrpDisplayAction} from "@mrp_workorder/mrp_display/mrp_display_action";
import {patch} from "@web/core/utils/patch";

patch(MrpDisplayAction.prototype, {
  get fieldsStructure() {
    const vals = super.fieldsStructure;
    vals["mrp.production"].push("customer_ids");
    vals["mrp.workorder"].push("customer_ids");
    vals["res.partner"] = ["id", "display_name"];
    return vals;
  },
});
