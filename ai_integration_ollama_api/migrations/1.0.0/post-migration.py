def migrate(cr, version):
    # Add num_predict column if it doesn't exist
    cr.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name='ai_provider_instance' 
                AND column_name='num_predict'
            ) THEN
                ALTER TABLE ai_provider_instance 
                ADD COLUMN num_predict integer DEFAULT 1024;
            END IF;
        END
        $$;
    """)
