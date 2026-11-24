import { registry } from "@web/core/registry";
import { FloatField, floatField } from "@web/views/fields/float/float_field";
import { MonetaryField, monetaryField } from "@web/views/fields/monetary/monetary_field";

/**
 * Unit-price fields that show the line's cost-basis evidence on hover.
 *
 * The server computes and translates everything (`cost_source_explanation`);
 * the client only renders it. When the payload is absent -- the field is not
 * in the view, the user is not a salesperson, or the line carries no
 * indicator -- the field renders exactly like its parent.
 */
function withCostSourceTooltip(Base) {
    return class extends Base {
        get costSourceExplanation() {
            return this.props.record.data.cost_source_explanation || false;
        }
        get costSourceTooltipInfo() {
            return JSON.stringify({ x: this.costSourceExplanation });
        }
    };
}

export class CostSourcePriceField extends withCostSourceTooltip(FloatField) {
    static template = "sale_cost_source.CostSourcePriceField";
}

export class CostSourceMonetaryField extends withCostSourceTooltip(MonetaryField) {
    static template = "sale_cost_source.CostSourceMonetaryField";
}

registry.category("fields").add("cost_source_price", {
    ...floatField,
    component: CostSourcePriceField,
});
registry.category("fields").add("cost_source_monetary", {
    ...monetaryField,
    component: CostSourceMonetaryField,
});
