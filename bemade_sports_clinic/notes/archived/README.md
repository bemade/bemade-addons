# Archived Documentation

This directory contains historical documentation from the development and debugging phases of the portal access system.

## Files

### MAIL_ACTIVITY_PORTAL_ACCESS.md
Original detailed analysis of mail.activity access requirements and implementation. This document was created during the initial development phase and contains comprehensive technical details about ACL permissions, record rules, and system dependencies.

**Status**: Largely superseded by centralized `AccessControlMixin` implementation.

### PORTAL_ACCESS_LIMITATIONS.md
Documentation of known limitations and issues with portal user access to mail-related models. Updated during the refactoring phase to reflect current access control status and test results.

**Status**: Contains current limitation analysis but moved to archive for organization.

## Current Documentation

For current portal access status and implementation details, see:
- `../PORTAL_ACCESS_CURRENT_STATUS.md` - Current implementation summary
- `../../security/mail_activity_portal_rules.xml` - Updated header comments with current status

## Historical Context

These documents were created during:
1. Initial mail.activity portal access implementation
2. Security vulnerability discovery and resolution
3. Access control refactoring with centralized `AccessControlMixin`
4. Test suite development and debugging

They are preserved for historical reference and to understand the evolution of the access control system.
