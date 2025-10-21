/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { useService } from "@web/core/utils/hooks";

class ProjectTaskListController extends ListController {
    setup() {
        super.setup();
        this.action = useService("action");
        console.log("[bemade_fsm] ProjectTaskListController setup - context:", this.props?.context);
    }

    async onCreateFromTemplate() {
        const ctx = this.props.context || {};
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "project.task.from.template.wizard",
            views: [[false, "form"]],
            target: "new",
            context: { ...ctx, res_model: "project.task" },
        });
    }
}

export const projectTaskListView = {
    ...listView,
    Controller: ProjectTaskListController,
    buttonTemplate: "bemade_fsm.ProjectTaskList.Buttons",
};

console.log("[bemade_fsm] Registering view: bemade_fsm_project_task_list");
registry.category("views").add("bemade_fsm_project_task_list", projectTaskListView);
