def migrate(cr, version):
    """Add explanation column to product_category_suggestion_history table."""
    if not version:
        return

    # Add explanation column if it doesn't exist
    cr.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='product_category_suggestion_history' 
        AND column_name='explanation'
    """)
    if not cr.fetchone():
        cr.execute("""
            ALTER TABLE product_category_suggestion_history 
            ADD COLUMN explanation text
        """)
