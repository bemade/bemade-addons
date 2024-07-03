/** @odoo-module **/

import {MrpDisplayAction} from "@mrp_workorder/mrp_display/mrp_display_action";
import {patch} from "@web/core/utils/patch";

patch(MrpDisplayAction.prototype, {
  get fieldsStructure() {
    const vals = super.fieldsStructure;
    vals["mrp.production"].push("customer_ids", "source_sale_orders");
    vals["res.partner"] = ["id", "display_name", "source_sale_orders"];
    return vals;
  },
});
