import { describe, expect, test } from "@odoo/hoot";
import { animationFrame, mockTouch } from "@odoo/hoot-mock";
import { EventBus } from "@odoo/owl";
import {
    contains,
    defineModels,
    fields,
    mockService,
    models,
    mountView,
} from "@web/../tests/web_test_helpers";
import { SIZES } from "@web/core/ui/ui_service";

describe.current.tags("desktop");

class Partner extends models.Model {
    name = fields.Char();
    trululu = fields.Many2one({ string: "Trululu", relation: "partner" });

    _records = [
        { id: 1, name: "first record", trululu: 4 },
        { id: 2, name: "second record", trululu: 1 },
        { id: 4, name: "aaa" },
    ];
}

defineModels([Partner]);

/**
 * Force `env.isSmall` on for the whole app, mirroring core's own small-screen
 * mock (see web/static/tests/views/form/form_view.test.js). Touch is controlled
 * independently via `mockTouch`, so the two axes can be varied separately.
 */
function mockSmallScreen() {
    const bus = new EventBus();
    mockService("ui", (env) => {
        Object.defineProperty(env, "isSmall", { value: true });
        return {
            bus,
            get size() {
                return SIZES.XS;
            },
            get isSmall() {
                return true;
            },
        };
    });
}

const FORM_ARCH = /* xml */ `<form><field name="trululu"/></form>`;

test(`narrow non-touch window keeps the inline autocomplete`, async () => {
    mockSmallScreen();
    mockTouch(false);

    await mountView({ resModel: "partner", type: "form", arch: FORM_ARCH, resId: 1 });

    // The editable AutoComplete input renders...
    expect(`.o_field_many2one[name=trululu] .o-autocomplete--input`).toHaveCount(1);
    // ...and the read-only mobile search input does NOT.
    expect(`.o_field_many2one[name=trululu] input[readonly]`).toHaveCount(0);
});

test(`touch small screen keeps the mobile search-dialog input`, async () => {
    mockSmallScreen();
    mockTouch(true);

    await mountView({ resModel: "partner", type: "form", arch: FORM_ARCH, resId: 1 });

    // The read-only dialog-opening input renders...
    expect(`.o_field_many2one[name=trululu] input[readonly]`).toHaveCount(1);
    // ...and the inline AutoComplete input does NOT.
    expect(`.o_field_many2one[name=trululu] .o-autocomplete--input`).toHaveCount(0);
});

test(`small-screen search dialog opens list-first, not kanban`, async () => {
    mockSmallScreen();
    mockTouch(true);

    await mountView({ resModel: "partner", type: "form", arch: FORM_ARCH, resId: 1 });

    await contains(`.o_field_many2one[name=trululu] input[readonly]`).click();
    await animationFrame();

    expect(`.modal .o_list_view`).toHaveCount(1);
    expect(`.modal .o_kanban_view`).toHaveCount(0);
});
