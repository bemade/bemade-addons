# -*- coding: utf-8 -*-
{
    'name': 'Test CalDAV Sync Appointments Integration',
    'version': '18.0.1.0.0',
    'category': 'Hidden/Tests',
    'summary': 'Test module for CalDAV sync integration with appointments',
    'description': """
Test CalDAV Sync Appointments Integration
=========================================

This module contains tests for the integration between CalDAV sync and the 
Appointments app. It verifies that appointment events are properly handled
during CalDAV synchronization operations.

This is a test-only module and should not be installed in production.
    """,
    'author': 'Bemade Inc.',
    'website': 'https://www.bemade.org',
    'depends': [
        'caldav_sync',
        'appointment',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    # Mark as test module
    'post_init_hook': None,
}
