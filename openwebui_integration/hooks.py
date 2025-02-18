# -*- coding: utf-8 -*-

def post_init_hook(cr, registry):
    """Post-init hook for initializing new columns."""
    # Initialize ollama_port with default value
    cr.execute("""
        ALTER TABLE res_company
        ADD COLUMN IF NOT EXISTS ollama_port integer DEFAULT 11434;
    """)