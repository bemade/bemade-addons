/** @odoo-module **/

import {MrpDisplayAction} from "@mrp_workorder/mrp_display/mrp_display_action";
import {patch} from "@web/core/utils/patch";

patch(MrpDisplayAction.prototype, {
  get fieldsStructure() {
    const vals = super.fieldsStructure;
    vals["mrp.production"].push("customer_ids", "source_sale_ids");
    vals["res.partner"] = ["id", "display_name"];
    vals["sale.order"] = ["id", "display_name"];
    return vals;
  },
});
