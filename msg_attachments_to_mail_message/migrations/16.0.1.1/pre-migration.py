from odoo import SUPERUSER_ID, api

def migrate(cr, version):
    if not version:
        return

    # Add msg_processed column
    cr.execute("""
        ALTER TABLE ir_attachment 
        ADD COLUMN IF NOT EXISTS msg_processed boolean DEFAULT false
    """)

    # Add mail_message_id column
    cr.execute("""
        ALTER TABLE ir_attachment 
        ADD COLUMN IF NOT EXISTS mail_message_id integer
    """)

    # Add foreign key constraint
    cr.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 
                FROM information_schema.constraint_column_usage 
                WHERE table_name = 'ir_attachment' 
                AND column_name = 'mail_message_id' 
                AND constraint_name = 'ir_attachment_mail_message_id_fkey'
            ) THEN
                ALTER TABLE ir_attachment
                ADD CONSTRAINT ir_attachment_mail_message_id_fkey 
                FOREIGN KEY (mail_message_id) 
                REFERENCES mail_message(id) ON DELETE SET NULL;
            END IF;
        END $$;
    """)
