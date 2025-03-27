# -*- coding: utf-8 -*-

import json
import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)

class UnifiCommonMixin(models.AbstractModel):
    """Mixin for common functionality across UniFi models
    
    This mixin provides common fields and methods that are used by multiple
    UniFi models, such as formatting raw JSON data.
    """
    _name = 'unifi.common.mixin'
    _description = 'UniFi Common Functionality Mixin'
    
    def format_raw_data_json(self, raw_data):
        """Format raw JSON data by removing outer braces and adjusting indentation
        
        Args:
            raw_data (str): Raw JSON data string
            
        Returns:
            str: Formatted JSON string without outer braces
        """
        if not raw_data:
            return ''
            
        try:
            # Load and format the JSON data
            data = json.loads(raw_data)
            formatted_json = json.dumps(data, indent=4)
            
            # Remove the first and last line (the braces)
            lines = formatted_json.split('\n')
            if len(lines) > 2:  # Ensure there are at least 3 lines
                # Remove the first and last line and adjust indentation
                inner_content = '\n'.join(line[4:] for line in lines[1:-1])
                return inner_content
            else:
                return formatted_json
        except (ValueError, json.JSONDecodeError):
            return 'Invalid JSON'
