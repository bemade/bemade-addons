Prepares what a technician must bring to a field service visit.

- **To bring list.** Each field service visit has a « To bring » tab: a checklist of
  tools and materials. Ticking an item records who checked it and when (set by the
  server). The list is not billed: it never creates sale order, delivery or invoice
  lines.
- **Task templates pre-fill it.** A task template carries its own « To bring » lines.
  Applying the template (the _From Template_ field, the _New task from template_ wizard,
  or a sale order whose product has a task template) copies the lines of the template
  and of its sub-templates onto the visit (the top-level task of the hierarchy).
- **Service tools.** Field Service > Configuration > Service Tools lists the tools the
  company owns, with the quantity owned and a return delay in days (1 by default).
  Field service managers maintain it; field service users read it.
- **Overbooking warning.** A tool is busy from a visit's start date until its end date
  plus the tool's return delay. When visits planned on overlapping dates (start date to
  end date, as in Planning, the end extended by that delay) need more of a tool than the quantity owned, the line turns red
  and the visit shows a banner naming the conflicting visits. Visits without both
  dates, done or cancelled visits, and the visit's own sub-tasks are not counted.
  Nothing is blocked.
