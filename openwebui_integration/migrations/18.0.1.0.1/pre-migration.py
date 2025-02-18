def migrate(cr, version):
    """Add products_per_request column to res_company table."""
    if not version:
        return

    # Add products_per_request column if it doesn't exist
    cr.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='res_company' 
        AND column_name='openwebui_products_per_request'
    """)
    if not cr.fetchone():
        cr.execute("""
            ALTER TABLE res_company 
            ADD COLUMN openwebui_products_per_request integer DEFAULT 10
        """)
