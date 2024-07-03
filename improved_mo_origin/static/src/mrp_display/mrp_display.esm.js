/** @odoo-module **/

import {MrpDisplay} from "@mrp_workorder/mrp_display/mrp_display";
import {patch} from "@web/core/utils/patch";

patch(MrpDisplay.prototype, {
  _makeModelParams() {
    var params = super._makeModelParams();
    const customerFields = this.props.models.find(
      (m) => m.resModel === "res.partner"
    ).fields;
    params.config.activeFields.customer_ids.related = {
      fields: customerFields,
      activeFields: customerFields,
    };
    const saleOrderFields = this.props.models.find(
      (m) => m.resModel === "sale.order"
    ).fields;
    params.config.activeFields.source_sale_ids.related = {
      fields: saleOrderFields,
      activeFields: saleOrderFields,
    };
    return params;
  },
});
