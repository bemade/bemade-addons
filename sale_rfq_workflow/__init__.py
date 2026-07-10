from . import models
from . import wizard


def _backfill_sale_line_id(env):
    """Link pre-existing supply RFQ lines through the core ``sale_line_id``
    so procurement adoption covers orders generated before this module
    was installed (the fields previously lived in a client module)."""
    env.cr.execute(
        """
        UPDATE purchase_order_line
           SET sale_line_id = supply_so_line_id
         WHERE supply_so_line_id IS NOT NULL
           AND sale_line_id IS NULL
        """
    )
