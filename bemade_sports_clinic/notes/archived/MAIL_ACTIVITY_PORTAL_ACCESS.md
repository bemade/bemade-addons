# Mail Activity Portal Access for Treatment Professionals

## Overview

**STATUS: LARGELY SUPERSEDED BY CENTRALIZED ACCESS CONTROL**

This document originally provided detailed analysis of mail.activity access requirements. The module has since been refactored with a centralized `AccessControlMixin` that handles all portal access control through team-based security.

**Current Implementation:**
- All controllers inherit from `AccessControlMixin` for consistent security
- Team-based access control enforced throughout
- Mail system limitations documented in `PORTAL_ACCESS_LIMITATIONS.md`
- 76/77 tests passing with robust security enforcement

## Historical Analysis

The following sections document the original detailed analysis for reference:

## Security Architecture

### 1. Access Control Lists (ACLs)

The following ACL entries have been added to `ir.model.access.csv` for the `group_portal_treatment_professional` group:

#### Core Mail Activity Models
- **mail.activity**: Full CRUD access (1,1,1,1)
- **mail.activity.type**: Read-only access (1,0,0,0)

#### Mail Infrastructure Dependencies
- **mail.message**: Full CRUD access (1,1,1,0) - No delete to preserve audit trail
- **mail.message.subtype**: Read-only access (1,0,0,0)
- **mail.template**: Read-only access (1,0,0,0)
- **mail.notification**: Create/Read/Write access (1,1,1,0)
- **mail.followers**: Create/Read/Write access (1,1,1,0) - No delete to preserve subscriptions
- **mail.alias**: Read-only access (1,0,0,0)
- **mail.alias.domain**: Read-only access (1,0,0,0)

#### System Dependencies
- **ir.model**: Read-only access (1,0,0,0) - Required for model ID resolution
- **ir.attachment**: Full CRUD access (1,1,1,1) - For activity attachments
- **res.users**: Read-only access (1,0,0,0) - For user assignment
- **res.partner**: Read-only access (1,0,0,0) - For partner relationships
- **bus.bus**: Create/Read/Write access (1,1,1,0) - For real-time notifications

### 2. Record Rules

Record rules are defined in `security/mail_activity_portal_rules.xml` to restrict access based on team, player, and injury relationships:

#### mail.activity Access Rule
Portal treatment professionals can access activities that are:
- Assigned to them directly (`user_id = user.id`)
- Related to patients they have access to through team assignments
- Related to injuries of patients they have access to through team assignments

#### mail.activity.type Access Rule
Portal treatment professionals can access activity types that are:
- Generic (no specific model restriction)
- Specific to `sports.patient` model
- Specific to `sports.patient.injury` model

#### mail.message Access Rule
Portal treatment professionals can access messages that are:
- On patients they have access to
- On injuries they have access to  
- On activities they have access to
- Authored by themselves

#### ir.attachment Access Rule
Portal treatment professionals can access attachments that are:
- Related to patients they have access to
- Related to injuries they have access to
- Related to activities they have access to
- Created by themselves

#### mail.followers Access Rule
Portal treatment professionals can access follower records that are:
- On patients they have access to
- On injuries they have access to
- Where they are the partner

## Implementation Details

### 1. Controller Modifications

The `TaskManagementPortal` controller has been modified to:
- Use normal user permissions for all validation and access checks
- Use `sudo()` only for the final `mail.activity.create()` call to bypass notification system restrictions
- Pass `today` variable to templates to replace `context_today()` calls
- Implement proper access validation for related models

### 2. Template Fixes

All QWeb templates have been updated to:
- Replace `context_today()` calls with `today` variable from controller context
- Use proper date formatting for activity deadlines and filtering

### 3. Security Considerations

#### Privilege Escalation
- `sudo()` is used minimally and only for activity creation
- All validation and access checks occur before privilege escalation
- Only the `mail.activity.create()` call is elevated to bypass notification access issues

#### Data Isolation
- Record rules ensure portal users only see activities related to their authorized teams/patients/injuries
- No access to activities outside their scope of responsibility
- Proper filtering based on team staff relationships

#### Audit Trail
- Mail messages are preserved (no delete access)
- Activity history is maintained
- User actions are logged through standard Odoo mechanisms

## Known Limitations and Workarounds

### 1. Odoo Standard Behavior
- Standard Odoo modules (project, hr, portal) do NOT grant portal users direct access to `mail.activity`
- This implementation extends beyond standard Odoo security patterns
- Custom implementation required for portal activity management

### 2. Notification System Issues
- Odoo's mail notification system has access restrictions for portal users
- `sudo()` workaround required for activity creation to bypass `mail.message.subtype` access issues
- Context flags (`mail_create_nolog`, `mail_activity_automation_skip`) alone are insufficient

### 3. Performance Considerations
- Record rule domains use complex queries with team/patient relationships
- May impact performance with large datasets
- Consider indexing on key relationship fields if performance issues arise

## Testing Requirements

### 1. Access Validation
- Verify portal users can create activities on authorized patients/injuries
- Verify portal users cannot access activities outside their scope
- Test activity assignment to other users
- Test activity updates and completion

### 2. Security Testing
- Attempt to access unauthorized activities
- Test record rule enforcement
- Verify ACL restrictions are properly applied
- Test privilege escalation boundaries

### 3. Integration Testing
- Test activity notifications and subscriptions
- Verify attachment handling
- Test activity chaining and automation
- Validate mail message creation and threading

## Future Considerations

### 1. Alternative Approaches
- Custom portal task/activity system independent of `mail.activity`
- Use internal users for treatment professionals instead of portal users
- Implement activity proxy models with restricted access

### 2. Compliance and Auditing
- Enhanced audit logging for portal user actions
- Data retention and anonymization for GDPR/Law 25 compliance
- Activity access logging and monitoring

### 3. Performance Optimization
- Optimize record rule queries
- Consider caching for team/patient relationships
- Database indexing for performance-critical fields

## Conclusion

This implementation provides comprehensive CRUD access to `mail.activity` objects for portal treatment professionals while maintaining security boundaries and data isolation. The approach extends Odoo's standard security model to accommodate the unique requirements of sports clinic portal users, with careful consideration of access control, audit trails, and system integrity.
