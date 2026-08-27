Glue between ``mrp_bom_variant_rule`` and ``sale``. Installs itself
automatically when both are present and adds nothing of its own beyond the
connection between them.

Configuring a variant on a quotation line is the moment a salesperson needs
its bill of materials to exist: it is what the line will be costed and priced
from. This module makes that the trigger. Setting a configured product on an
order line generates the variant's bill of materials if the ruleset can
produce one, and surfaces its state on the line — generated, superseded,
refused for an unmatched slot, or costed from stale component prices — so the
person quoting sees what stands behind the number before the quotation goes
out. A control on the line regenerates on demand after a ruleset correction.

Generation is deliberately *not* hooked into price computation itself.
Pricelist evaluation runs in read paths — reports, portal pages, scheduled
recomputation — where creating records as a side effect would be surprising
and, in a report or a cron, wrong. Binding the trigger to the sales document
keeps generation tied to a person deliberately configuring something.
