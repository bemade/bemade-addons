// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
/**
 * Tours for the subtask tree of FSM tasks (task 924).
 *
 * fsm_task_subtask_tree_tour -- on a top-level FSM task form, the Sub-tasks
 * tab lists the interventions; each unfolds to its tasks (2 levels, the tasks
 * have no expand button even when they have subtasks), and folds back.
 *
 * fsm_task_subtask_tree_intervention_tour -- on an intervention's form, the
 * Sub-tasks tab is the plain list of its tasks (not recursive).
 *
 * Data is seeded by test_fsm_task_subtask_tree_tour.py.
 */
import { registry } from "@web/core/registry";

const LIST = ".o_field_widget[name='child_ids'] .o_list_renderer";

registry.category("web_tour.tours").add("fsm_task_subtask_tree_tour", {
    steps: () => [
        {
            content: "Open the Sub-tasks tab of the top-level task",
            trigger: ".o_form_view .o_notebook .nav-link[name='sub_tasks_page']",
            run: "click",
        },
        {
            content: "The subtask list is recursive (expand column present)",
            trigger: `${LIST} th.o_recursive_expand_column`,
        },
        {
            content: "Both interventions are listed with an expand button",
            trigger: `${LIST} tbody:has(button.o_expand_button[data-depth='0']:eq(1))`,
        },
        {
            content: "Their tasks are folded initially",
            trigger: `${LIST} tbody:not(:has(tr.o_recursive_child_row))`,
        },
        {
            content: "Unfold intervention 1",
            trigger: `${LIST} tr.o_data_row:has(td:contains('Synthetic Intervention 1')) button.o_expand_button`,
            run: "click",
        },
        {
            content: "Its two tasks are shown below it",
            trigger: `${LIST} tbody:has(tr.o_recursive_child_row:contains('Synthetic Task 1.1')):has(tr.o_recursive_child_row:contains('Synthetic Task 1.2'))`,
        },
        {
            content: "Tasks of intervention 2 stay folded",
            trigger: `${LIST} tbody:not(:has(tr.o_recursive_child_row:contains('Synthetic Task 2.1')))`,
        },
        {
            content: "Depth is capped at 2: a task with subtasks has no expand button",
            trigger: `${LIST} tr.o_recursive_child_row:contains('Synthetic Task 1.1'):not(:has(button.o_expand_button))`,
        },
        {
            content: "Fold intervention 1",
            trigger: `${LIST} tr.o_data_row:has(td:contains('Synthetic Intervention 1')) button.o_expand_button`,
            run: "click",
        },
        {
            content: "Its tasks are hidden again",
            trigger: `${LIST} tbody:not(:has(tr.o_recursive_child_row))`,
        },
        {
            content: "Unfold intervention 2",
            trigger: `${LIST} tr.o_data_row:has(td:contains('Synthetic Intervention 2')) button.o_expand_button`,
            run: "click",
        },
        {
            content: "Its two tasks are shown",
            trigger: `${LIST} tbody:has(tr.o_recursive_child_row:contains('Synthetic Task 2.1')):has(tr.o_recursive_child_row:contains('Synthetic Task 2.2'))`,
        },
        {
            content: "Add an intervention from the list",
            trigger: `${LIST} .o_field_x2many_list_row_add a`,
            run: "click",
        },
        {
            content: "Name the new intervention",
            trigger: `${LIST} tr.o_selected_row td[name='name'] input`,
            run: "edit Synthetic Intervention 3",
        },
        {
            content: "Save the task",
            trigger: ".o_form_view .o_form_button_save",
            run: "click",
        },
        {
            content: "The new intervention is listed with the others, the tree still works",
            trigger: `${LIST} tbody:has(tr.o_data_row:contains('Synthetic Intervention 3')):has(tr.o_recursive_child_row:contains('Synthetic Task 2.1'))`,
        },
        {
            content: "The form is saved",
            trigger: ".o_form_view .o_form_saved",
        },
    ],
});

registry.category("web_tour.tours").add("fsm_task_subtask_tree_intervention_tour", {
    steps: () => [
        {
            content: "Open the Sub-tasks tab of the intervention",
            trigger: ".o_form_view .o_notebook .nav-link[name='sub_tasks_page']",
            run: "click",
        },
        {
            content: "Its tasks are listed",
            trigger: `${LIST} tr.o_data_row:contains('Synthetic Task 1.1')`,
        },
        {
            content: "The list is not recursive on an intervention",
            trigger: `${LIST}:not(:has(.o_recursive_expand_column))`,
        },
    ],
});
