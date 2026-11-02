def migrate(cr, version):
    """Carry the old ``smtp_ssl`` checkbox over to ``smtp_encryption``.

    ``smtp_ssl`` meant STARTTLS when set and no encryption when not, so
    existing mailboxes keep exactly the behaviour they had. Runs before the
    ORM creates the new column (which would otherwise default every row to
    STARTTLS), and does nothing once the column exists.
    """
    cr.execute(
        """
        SELECT column_name FROM information_schema.columns
         WHERE table_name = 'conversation_transport'
           AND column_name IN ('smtp_ssl', 'smtp_encryption')
        """
    )
    columns = {row[0] for row in cr.fetchall()}
    if "smtp_encryption" in columns or "smtp_ssl" not in columns:
        return
    cr.execute("ALTER TABLE conversation_transport ADD COLUMN smtp_encryption varchar")
    cr.execute(
        """
        UPDATE conversation_transport
           SET smtp_encryption = CASE WHEN smtp_ssl THEN 'starttls' ELSE 'none' END
        """
    )
