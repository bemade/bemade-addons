/** @odoo-module **/

import { ListArchParser} from "@web/views/list/list_arch_parser";
import { patch } from "@web/core/utils/patch";

patch(ListArchParser.prototype, {
    parse(xmlDoc, models, modelName) {
        const result = super.parse(...arguments);

        const recursiveAttr = xmlDoc.getAttribute("recursive")
        if ( recursiveAttr ) {
            result.recursive = recursiveAttr === "1" || recursiveAttr === "true" || recursiveAttr === "True";
        }
        return result;
    }
})