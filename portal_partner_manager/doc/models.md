# Portal Partner Manager Module - Models Documentation

This document provides detailed information about the models implemented in the Portal Partner Manager module. This module enhances Odoo's portal functionality by allowing portal users to manage their company information and contacts.

## 1. Portal Editable Mixin (`portal.editable.mixin`)

This mixin provides a standardized way to add portal editing capabilities to any model. It includes fields for tracking portal updates and methods for controlling access.

### 1.1 Fields

| Field Name | Type | Description |
|------------|------|-------------|
| `portal_last_update` | Datetime | Tracks when a portal user last updated the record |
| `portal_updated_by` | Many2one | References the portal user who made the last update |
| `allow_portal_edit` | Boolean | Controls whether portal users can edit this record |

### 1.2 Key Methods

#### `write(vals)`
Overrides the standard write method to:
- Check if the user has permission to edit the record
- Add tracking information when updated via the portal
- Filter fields that can be edited via the portal

#### `_check_portal_edit_access(user)`
Checks if a specific user has permission to edit the record. To be overridden by inheriting models to implement specific access rules.

#### `_get_portal_allowed_fields()`
Returns the list of fields that portal users are allowed to edit. To be overridden by inheriting models to specify allowed fields.

## 2. Enhanced Partner Model (`res.partner`)

The module extends the standard `res.partner` model to add portal-specific functionality.

### 2.1 Added Fields

| Field Name | Type | Description |
|------------|------|-------------|
| `allow_portal_parent_edit` | Boolean | Legacy field, related to `allow_portal_edit` for backward compatibility |

### 2.2 Key Methods

#### `_check_portal_edit_access(user)`
Overrides the mixin's method to implement partner-specific access rules:
- Users can always edit their own profile
- Users can edit their parent company if it allows editing
- Users can edit contacts of their parent company if the parent allows it

#### `_get_portal_allowed_fields()`
Returns the list of fields that portal users are allowed to edit:
- Basic information: name, comment
- Contact details: phone, mobile, email, website
- Address fields: street, street2, zip, city, state_id, country_id
- Company information: vat

#### `get_portal_children(user_id=None)`
Returns the child contacts visible to a specific portal user:
- For administrators, returns all child contacts
- For portal users, returns child contacts only if the user is associated with the company
- Returns empty recordset if the user doesn't have access

#### `create_portal_contact(parent_id, vals)`
Creates a new child contact via the portal:
- Validates that the user has permission to add contacts to the company
- Ensures required fields like email are provided
- Filters the input values to only allow editing of permitted fields

## 3. Portal Access Configuration (`portal.access`)

This model manages access configurations for portal users, controlling what they can view and edit.

### 3.1 Fields

| Field Name | Type | Description |
|------------|------|-------------|
| `name` | Char | Name of the access configuration |
| `active` | Boolean | Whether this configuration is active |
| `partner_id` | Many2one | The company for which this configuration applies |
| `allow_edit` | Boolean | Whether portal users can edit company information |
| `allow_add_contacts` | Boolean | Whether portal users can add contacts to the company |
| `allowed_fields_ids` | Many2many | Specific fields that portal users are allowed to edit |
| `portal_user_ids` | Many2many | Portal users who have access to this configuration |
| `log_ids` | One2many | Access logs related to this configuration |

### 3.2 Key Methods

#### `create(vals)` and `write(vals)`
Overrides the standard methods to automatically update the related partner's `allow_portal_parent_edit` field when the configuration changes.

#### `get_allowed_fields(partner_id=None)`
Returns the list of fields allowed to be edited for a specific partner:
- If specific fields are configured, returns those fields
- Otherwise, returns a default list of common fields

#### `log_access(user_id, action, details=None)`
Records an entry in the access log when a portal user accesses or modifies company information.

## 4. Portal Activity Log (`portal.activity.log`)
This model tracks portal user activity related to company and other records in the portal.

### 4.1 Fields

| Field Name     | Type       | Description                                                           |
|----------------|------------|-----------------------------------------------------------------------|
| `user_id`      | Many2one   | The user who performed the action                                     |
| `ip`           | Char       | IP address of the user performing the action                          |
| `model`        | Char       | Model of the record the action pertains to                            |
| `res_id`       | Integer    | ID of the record                                                      |
| `action`       | Selection  | Type of action: view, edit, edit_user, create, archive, unarchive, grant_access, revoke_access, other |
| `details`      | Text       | Additional details about the action                                   |
| `create_date`  | Datetime   | When the action was performed                                         |
| `resource_name`| Char       | Display name of the record or indication if it was deleted            |

### 4.2 Portal Logging Mixin (`portal.logging.mixin`)

Abstract model providing a logging method on any model.

- `log_portal_activity(user_id, action, details=None, ip=None)`: creates a new `portal.activity.log` entry for the current record.

## Implementation Notes

1. **Security**: The module implements careful permission checking to ensure portal users can only access and modify information they're authorized to.

2. **Tracking**: All modifications made via the portal are tracked with timestamps and user information.

3. **Flexibility**: The configuration system allows administrators to precisely control which fields portal users can edit.

4. **Auditability**: The logging system provides a complete audit trail of portal user activity.

5. **Integration**: The module seamlessly integrates with Odoo's existing portal framework, enhancing it with company management capabilities.

6. **Reusability**: The `portal.editable.mixin` can be used to quickly add portal editing capabilities to any model in other modules.
