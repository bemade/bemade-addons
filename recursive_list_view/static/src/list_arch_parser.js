/** @odoo-module **/

import { ListArchParser } from "@web/views/list/list_arch_parser";
import { patch } from "@web/core/utils/patch";

const TRUE_VALUES = ["1", "true", "True"];
const FALSE_VALUES = ["", "0", "false", "False"];

patch(ListArchParser.prototype, {
    parse(xmlDoc, models, modelName) {
        const result = super.parse(...arguments);

        const recursiveAttr = (xmlDoc.getAttribute("recursive") || "").trim();
        if (TRUE_VALUES.includes(recursiveAttr)) {
            result.recursive = true;
        } else if (FALSE_VALUES.includes(recursiveAttr)) {
            result.recursive = false;
        } else {
            // A domain-like python expression: only meaningful on a list embedded
            // in a form (x2many), where it is evaluated on the parent record.
            result.recursive = false;
            result.recursiveExpr = recursiveAttr;
        }
        const depth = parseInt(xmlDoc.getAttribute("recursive_depth"), 10);
        if (depth > 0) {
            result.recursiveDepth = depth;
        }
        return result;
    },
});
