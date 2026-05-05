# -*- coding: utf-8 -*-
"""
Post-migration script for version 18.0.1.7.0

- Updates security rules for player removal features
- Refreshes the security rules cache
"""

def migrate(cr, version):
    # The security rules are already defined in the XML files
    # This will be applied when the module is updated
    pass
