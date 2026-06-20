# Changelog - bemade_fsm

## [18.0.0.4.4] - 2026-01-27

### Fixed

#### Task Sorting in PDF Reports
- **Problem**: When printing FSM Work Orders to PDF, tasks appeared in random or reversed order.
- **Solution**: Tasks are now sorted by the `sequence` field, allowing users to define a custom order.
- **Files modified**:
  - `reports/worksheet_custom_reports.py`: Added sorting by `sequence` then `id` in `_get_report_values()`

#### Drag & Drop Reordering in Task List
- **Feature**: Added sequence handle widget to FSM task list view for drag & drop reordering.
- **Files modified**:
  - `views/task_views.xml`: Added `<field name="sequence" widget="handle" />` to `project_task_view_list_fsm_inherit`

#### Visit Ordering
- **Problem**: Visit numbers (`visit_no`) were calculated using sale order line sequence, which didn't reflect the actual chronological order.
- **Solution**: Visits are now ordered by their associated task's `planned_date_begin`.
- **Files modified**:
  - `models/fsm_visit.py`: Updated `_compute_visit_no()` to sort by `task_id.planned_date_begin`

### Added

#### Tests for Task Sorting
- Added unit tests to validate task sorting behavior in PDF reports.
- **Files added/modified**:
  - `tests/test_task_report.py`:
    - `test_report_tasks_sorted_by_sequence()`: Validates tasks are sorted by sequence field
    - `test_report_tasks_sorted_by_id_when_same_sequence()`: Validates fallback to id when sequences are equal

---

## Usage

### Reordering Tasks for PDF Reports
1. Navigate to the FSM task list view
2. Use the drag handle (☰) on the left of each task to reorder
3. Print the Work Order PDF — tasks will appear in the defined order

### Visit Ordering
Visits are automatically numbered based on their task's planned start date. Earlier dates appear first.
