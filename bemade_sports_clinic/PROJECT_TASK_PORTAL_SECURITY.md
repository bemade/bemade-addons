# Project Task Portal Security Architecture

## Overview
This document outlines the comprehensive security implementation for portal treatment professionals accessing project.task objects (events) in the bemade_sports_clinic module.

## Security Principles Applied

### 1. **Explicit Authorization Only**
- **NO** blanket access based on `privacy_visibility = 'portal'`
- **YES** explicit authorization through follower relationships or team membership
- **Principle**: Users must be explicitly granted access, not implicitly through project settings

### 2. **Multi-Layer Security Architecture**
1. **ACL Level**: Model-level CRUD permissions
2. **Record Rule Level**: Record-level filtering based on explicit relationships
3. **Field Level**: Field-level group access controls
4. **Controller Level**: Additional business logic validation

## Implementation Details

### Access Control Lists (ACLs)
**File**: `security/ir.model.access.csv`

```csv
# Portal Treatment Professionals get read/write/create access to project tasks
access_project_task_portal_tp,Portal TP Access for Project Tasks,project.model_project_task,bemade_sports_clinic.group_portal_treatment_professional,1,1,1,0

# Portal Treatment Professionals get read/write access to projects (for follower management)
access_project_project_portal_tp,Portal TP Access for Projects,project.model_project_project,bemade_sports_clinic.group_portal_treatment_professional,1,1,0,0

# Read-only access to supporting models
access_project_task_type_portal_tp,Portal TP Access for Task Types,project.model_project_task_type,bemade_sports_clinic.group_portal_treatment_professional,1,0,0,0
access_project_tags_portal_tp,Portal TP Access for Project Tags,project.model_project_tags,bemade_sports_clinic.group_portal_treatment_professional,1,0,0,0
access_project_milestone_portal_tp,Portal TP Access for Project Milestones,project.model_project_milestone,bemade_sports_clinic.group_portal_treatment_professional,1,0,0,0
```

### Record Rules
**File**: `security/project_task_portal_rules.xml`

#### Project Task Access Rule
```xml
<field name="domain_force">[
    '|', '|', '|',
    # Tasks assigned to the user
    ('user_ids', 'in', [user.id]),
    # Tasks where user is a follower
    ('message_partner_ids', 'in', [user.partner_id.id]),
    # Tasks from projects where user is a follower
    ('project_id.message_partner_ids', 'in', [user.partner_id.id]),
    # Tasks from projects where user's teams are partners
    ('project_id.partner_id', 'in', user.partner_id.team_staff_rel_ids.mapped('team_id.id') or [0])
]
```

#### Project Access Rule
```xml
<field name="domain_force">[
    '|',
    # Projects where user is explicitly a follower
    ('message_partner_ids', 'in', [user.partner_id.id]),
    # Projects where user's teams are partners
    ('partner_id', 'in', user.partner_id.team_staff_rel_ids.mapped('team_id.id') or [0])
]
```

### Field-Level Security
**Files**: `models/project_task.py` and `models/project_project.py`

All critical fields are overridden with explicit group access for authorized sports clinic users only:
```python
# SECURE: Only authorized sports clinic portal users, not all portal users
_portal_groups = 'base.group_user,bemade_sports_clinic.group_portal_treatment_professional,bemade_sports_clinic.group_portal_team_coach'

# Core fields
name = fields.Char(groups=_portal_groups)
description = fields.Html(groups=_portal_groups)
user_ids = fields.Many2many(groups=_portal_groups)
project_id = fields.Many2one(groups=_portal_groups)
# ... and many more
```

### Controller Security
**File**: `controllers/events_portal.py`

#### Secure Domain Construction
```python
def _prepare_events_domain(self, view_type='all'):
    # Base domain: tasks from projects where user has explicit authorization
    base_domain = [
        '|', '|',
        # Tasks from projects where user's teams are partners
        ('project_id.partner_id', 'in', team_ids or [0]),
        # Tasks from projects where user is a follower
        ('project_id.message_partner_ids', 'in', [partner.id]),
        # Tasks where user is directly assigned or following
        '|',
        ('user_ids', 'in', [user.id]),
        ('message_partner_ids', 'in', [partner.id])
    ]
```

#### Project Filtering
```python
def _get_available_projects(self):
    # Only show projects where user has explicit authorization
    domain = [
        '|',
        # Projects where user's teams are partners
        ('partner_id', 'in', team_ids or [0]),
        # Projects where user is explicitly a follower
        ('message_partner_ids', 'in', [partner.id])
    ]
```

## Security Validation

### Model-Level Access Checking
```python
def check_portal_task_access(self):
    # 1. Check user is assigned to task
    # 2. Check user is follower of task
    # 3. Check user is follower of project
    # 4. Check user's teams are partners of project
    # NO blanket portal visibility check
```

### Project Configuration
```python
def ensure_portal_access_for_treatment_professionals(self):
    # Only add treatment professionals who are staff on the team
    # NO blanket addition of all portal users
```

## Critical Security Fixes Applied

### ❌ **BEFORE (Vulnerable)**
```python
# SECURITY FLAW: Any portal user could access any portal-visible project
domain = [
    '|', '|',
    ('partner_id', 'in', team_ids),
    ('message_partner_ids', 'in', [partner.id]),
    ('privacy_visibility', '=', 'portal')  # ← VULNERABILITY
]
```

### ✅ **AFTER (Secure)**
```python
# SECURE: Only explicitly authorized users can access projects
domain = [
    '|',
    ('partner_id', 'in', team_ids or [0]),      # Team relationship
    ('message_partner_ids', 'in', [partner.id]) # Explicit follower
]
```

## Testing and Validation

### Security Test Utility
**File**: `models/project_task_security_test.py`
- Admin UI for testing field access
- Validates all security layers
- Tests unauthorized access scenarios

### Comprehensive Test Suite
**File**: `tests/test_project_task_portal_security.py`
- 10 test cases covering all security aspects
- Validates proper access isolation
- Tests record rule enforcement

## Best Practices Established

1. **Explicit Authorization Required**: Never grant access based solely on project privacy settings
2. **Follower-Based Security**: Use message_partner_ids for explicit access control
3. **Team-Based Authorization**: Link project access to sports team relationships
4. **Layered Security**: Multiple security layers working together
5. **Principle of Least Privilege**: Grant minimum necessary permissions

## Common Security Anti-Patterns Avoided

1. **❌ Portal Visibility OR Condition**: `('privacy_visibility', '=', 'portal')` as standalone OR
2. **❌ Blanket Group Access**: Adding all portal users as followers
3. **❌ Overly Broad Domains**: Using `[(1, '=', 1)]` or similar catch-all domains
4. **❌ Missing Fallbacks**: Not using `or [0]` for empty list protection

## Deployment Checklist

- [ ] Update module to install new security files
- [ ] Run security tests to validate implementation
- [ ] Verify portal users can only access authorized projects/tasks
- [ ] Test that unauthorized users are properly denied access
- [ ] Validate field-level access works correctly in portal UI

## Maintenance Guidelines

1. **Always use explicit authorization** when creating new access rules
2. **Test security boundaries** whenever adding new portal functionality
3. **Document security decisions** for future developers
4. **Regular security audits** of domain logic and record rules
5. **Follow the established patterns** for consistent security implementation
