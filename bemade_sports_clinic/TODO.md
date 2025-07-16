# Sports Clinic Module - TODO List

## High Priority

### Player Management
- [x] **Review permission checks** in `patient.remove_from_team()`
  - [x] Ensure proper access controls are in place for player removal
  - [x] Consider adding more granular permissions for different user roles
  - [x] Refactored to use cron jobs for permission-sensitive operations
  - [x] Fixed test cases for player removal workflow

### Injury Tracking
- [x] **Add parental consent field** to injuries
  - [x] Verified existing field: `parental_consent = fields.Selection([('yes', 'Yes'), ('no', 'No'), ('na', 'Not Applicable')])`
  - [x] Confirmed French Canadian (fr_CA) translations are in place for all UI elements
  - [x] Verified field is properly displayed in injury forms and lists
  - [x] Added field to the therapist portal UI for injury creation
  - [x] Updated portal controller to handle the parental consent field

- [ ] **Fix configuration issues**
  - [ ] Fix injury update chatter links pointing to example.com before going live


## Medium Priority

### Team Staff Management
- [x] **Review and refactor** `_update_treatment_professional_group`
  - [x] Refactored into smaller, more maintainable methods
  - [x] Improved code documentation and clarity
  - [x] Verified functionality with existing tests
  - [x] Removed unnecessary `web_responsive` dependency

## Testing Strategy

### Email Configuration
- [ ] **Fix email configuration in tests**
  - `test_treatment_prof_can_remove_player_from_team` is currently disabled due to email configuration issues
  - Need to properly configure test environment to handle email sending
  - Consider using `mail.trap` or similar for test emails
  - Re-enable test after configuration is fixed


### Unit Tests
- [x] **Player Management**
  - [x] Test player removal workflow
    - [x] Coach-initiated removal requests
    - [x] Treatment professional approval flow
    - [x] Permission enforcement
    - [x] Pending removal flag behavior
    - [x] Archiving of players with no teams
  - [x] Parental consent field functionality
  - [x] Match and practice availability tracking

- [x] **Injury Tracking**
  - [x] Enhanced notification system
  - [ ] Progress tracking and resolution monitoring
  - [x] Internal vs external notes functionality
  - [x] Treatment professional assignments

- [ ] **Data Protection**
  - [ ] GDPR and Quebec Law 25 compliance features
  - [ ] Data anonymization functionality
  - [ ] Configurable retention periods
  - [ ] Audit logging verification
  - [ ] Manual anonymization wizard

### Integration Tests
- [x] **Portal Features**
  - [x] Field therapist portal access
  - [x] Coach portal functionality
  - [x] Injury reporting through portal
  - [x] Player status updates

- [x] **Security**
  - [x] Field-level security validations
  - [x] Permission escalation prevention
  - [ ] Audit trail verification

### End-to-End Tests
- [x] Complete injury workflow (report → treatment → resolution)
- [x] Player removal workflow
- [x] Data export/anonymization process

### Performance Tests
- [ ] Large dataset handling
- [ ] Concurrent user access
- [ ] Report generation with extensive data

## Portal Requirements

### Therapist Portal

### Player Management
- [x] **Player CRUD Operations**
  - [x] Add new players to the system
  - [x] Remove players from teams
  - [x] Update player information (name, contact details, etc.)
  - [x] Manage player team assignments

### Injury Management
- [x] **Injury Tracking**
  - [x] Add new injuries
  - [x] Modify existing injury details
  - [x] Update injury status and progress
  - [x] Add treatment notes and updates
  - [x] Upload and manage injury-related documents

### Patient Information
- [x] **Patient Profile Management**
  - [x] Edit visible patient information
  - [x] Update emergency contacts
  - [x] Manage patient medical history
  - [x] Track and update insurance information

### Task Management
- [x] **Mail Activities (To-Dos)**
  - [x] Create new activities for patients/injuries
  - [x] Assign activities to internal users
  - [x] Assign activities to portal users with appropriate access
  - [x] Track activity status and completion
  - [x] Set due dates and priorities
  - [x] Add activity notes and updates

## Data Privacy & Compliance

### Data Retention & Anonymization
- [ ] **Implement scheduled data anonymization**
  - Create a scheduled action to automatically anonymize personal data after a configurable retention period
  - Add configuration settings for retention periods (default: 7 years for medical records, 2 years for non-medical data)
  - Ensure compliance with GDPR and Quebec's Law 25 (Loi 25)
  - Add logging of all anonymization actions for audit purposes
  - Create a manual anonymization wizard for one-off requests
  - Add data export functionality for records before anonymization

## Future Enhancements

### Player Management
- [ ] Add bulk operations for player management
- [ ] Add more detailed player status tracking

### Reporting
- [ ] Add reports for player injuries and team health status
- [ ] Create dashboard for treatment professionals

## Back Burner (Postponed)

### Injury Tracking
- [x] **Improve injury notification system**
  - [x] Review and enhance how injury tracking notifications are sent
  - [x] Consider adding more detailed tracking information

## Notes
- Keep this file updated as new TODOs are identified
- Reference relevant issue numbers when available
- Delete or check off items as they are completed
