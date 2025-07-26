# Mail Activity Portal Access Tests

This directory contains comprehensive tests for the mail activity portal access functionality implemented for treatment professionals in the bemade_sports_clinic module.

## Test Files Overview

### 1. `test_mail_activity_portal_access.py`
**Purpose**: Unit and integration tests for mail.activity CRUD operations via ORM  
**Test Count**: 20 comprehensive tests  
**Coverage**:
- Activity creation, reading, updating, deletion
- Access control validation (authorized vs unauthorized records)
- Activity type access and filtering
- Mail message and attachment access control
- Record rule domain evaluation
- Security validation and minimal sudo() usage
- Mail followers access control
- Bus notification access

**Key Test Categories**:
- **CRUD Operations** (tests 01-08): Basic create, read, update, delete operations
- **Access Control** (tests 03-06): Unauthorized access prevention
- **Related Models** (tests 09-13): Activity types, messages, attachments
- **Security Features** (tests 14-20): Record rules, search filtering, security validation

### 2. `test_mail_activity_portal_integration.py`
**Purpose**: HTTP integration tests for portal web interface  
**Test Count**: 16 comprehensive tests  
**Coverage**:
- Portal page access and navigation
- HTTP form submissions (create, update, complete, delete)
- Web interface security (CSRF protection)
- Activity filtering, searching, and pagination
- Error handling and user feedback
- Attachment handling in portal interface

**Key Test Categories**:
- **Portal Access** (tests 01-03): Page access and form rendering
- **HTTP Operations** (tests 04-09): Form submissions and data processing
- **Web Features** (tests 10-15): Filtering, search, pagination
- **Security & Error Handling** (tests 12, 16): CSRF protection and error handling

### 3. `test_mail_activity_portal_runner.py`
**Purpose**: Test runner and reporting utility  
**Features**:
- Run all tests or specific test classes/methods
- Environment validation
- Comprehensive test reporting
- Command-line interface for test execution

## Running the Tests

### Prerequisites
1. Ensure you're in the Odoo root directory
2. Have a test database configured
3. Module is installed and up-to-date

### Run All Tests
```bash
cd /Users/ddurepos/src/fitcrew
python addons/bemade_sports_clinic/tests/test_mail_activity_portal_runner.py
```

### Run Specific Test Class
```bash
# Run only unit tests
python addons/bemade_sports_clinic/tests/test_mail_activity_portal_runner.py --class TestMailActivityPortalAccess

# Run only integration tests
python addons/bemade_sports_clinic/tests/test_mail_activity_portal_runner.py --class TestMailActivityPortalIntegration
```

### Run Individual Tests via Odoo
```bash
# Run unit tests
python odoo-bin --test-enable --test-tags bemade_sports_clinic.tests.test_mail_activity_portal_access --stop-after-init --database test_db

# Run integration tests
python odoo-bin --test-enable --test-tags bemade_sports_clinic.tests.test_mail_activity_portal_integration --stop-after-init --database test_db
```

### Validate Environment
```bash
python addons/bemade_sports_clinic/tests/test_mail_activity_portal_runner.py --validate
```

### Generate Test Report Only
```bash
python addons/bemade_sports_clinic/tests/test_mail_activity_portal_runner.py --report
```

## Test Coverage Details

### Security Features Tested

#### 1. Access Control Lists (ACLs)
- ✅ `mail.activity` full CRUD access for portal treatment professionals
- ✅ `mail.activity.type` read access with model filtering
- ✅ `mail.message` access for activity-related messages
- ✅ `ir.attachment` access for activity attachments
- ✅ `mail.followers` access for subscription management
- ✅ `bus.bus` access for real-time notifications
- ✅ System dependencies (`ir.model`, `res.users`, `res.partner`)

#### 2. Record Rules
- ✅ Team-based access restrictions
- ✅ Patient/injury relationship validation
- ✅ User assignment-based access
- ✅ Complex domain evaluation with OR/AND logic
- ✅ Cross-team data isolation

#### 3. HTTP Security
- ✅ CSRF token validation on all form submissions
- ✅ Form input validation and sanitization
- ✅ Unauthorized access prevention
- ✅ Error handling without information disclosure

#### 4. Data Isolation
- ✅ Activities visible only to authorized users
- ✅ Messages accessible based on record access
- ✅ Attachments restricted to authorized records
- ✅ Search and filtering respect access rules

### Functional Features Tested

#### 1. Activity Management
- ✅ Create activities on patients and injuries
- ✅ Update activity details (summary, notes, deadlines)
- ✅ Complete activities with feedback
- ✅ Delete activities when authorized
- ✅ Activity assignment to different users

#### 2. Portal Interface
- ✅ Activity list with filtering and pagination
- ✅ Activity creation forms with validation
- ✅ Activity update forms with pre-population
- ✅ Activity completion workflow
- ✅ Search functionality across activities

#### 3. Integration Features
- ✅ Mail message creation on activity completion
- ✅ Attachment handling and access
- ✅ Follower subscription management
- ✅ Real-time notifications via bus system

## Test Data Setup

Each test class sets up comprehensive test data including:

### Organizations and Teams
- Authorized team (therapist has access)
- Unauthorized team (therapist has no access)

### Users and Roles
- Treatment professional with portal access
- Multiple therapists for cross-access testing
- Proper group assignments and team staff relationships

### Patients and Injuries
- Patients in authorized and unauthorized teams
- Active injuries with proper consent and team assignments
- Various injury stages and types for testing

### Activity Types
- Patient-specific activity types
- Injury-specific activity types
- Generic activity types
- Restricted activity types for negative testing

## Expected Test Results

### Success Criteria
- All 36 tests should pass (20 unit + 16 integration)
- No AccessError exceptions for authorized operations
- Proper AccessError exceptions for unauthorized operations
- All HTTP responses return expected status codes
- Database state matches expected outcomes

### Common Issues and Troubleshooting

#### 1. ACL-Related Failures
- **Symptom**: AccessError on basic operations
- **Solution**: Verify ACL entries in `ir.model.access.csv`
- **Check**: Module upgrade completed successfully

#### 2. Record Rule Failures
- **Symptom**: Cannot access authorized records
- **Solution**: Check record rule domains in `mail_activity_portal_rules.xml`
- **Check**: Team staff relationships are properly created

#### 3. HTTP Test Failures
- **Symptom**: 500 errors or unexpected redirects
- **Solution**: Check controller implementation and CSRF handling
- **Check**: Portal templates render without errors

#### 4. Environment Issues
- **Symptom**: Tests fail to start or timeout
- **Solution**: Verify test database and Odoo configuration
- **Check**: All dependencies are installed

## Maintenance and Updates

### When to Run Tests
- After any changes to security files (`ir.model.access.csv`, record rules)
- After controller modifications
- After template updates
- Before deploying to production
- As part of CI/CD pipeline

### Adding New Tests
1. Follow existing naming conventions (`test_##_descriptive_name`)
2. Include both positive and negative test cases
3. Test both ORM and HTTP interfaces where applicable
4. Update this documentation with new test descriptions

### Test Data Management
- Tests use `TransactionCase` for automatic rollback
- Each test is isolated and doesn't affect others
- Test data is created in `setUpClass` for efficiency
- Clean up is handled automatically by the test framework

## Integration with CI/CD

These tests are designed to be integrated into continuous integration pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run Mail Activity Portal Tests
  run: |
    python addons/bemade_sports_clinic/tests/test_mail_activity_portal_runner.py
    
- name: Generate Test Report
  run: |
    python addons/bemade_sports_clinic/tests/test_mail_activity_portal_runner.py --report
```

## Security Compliance

These tests validate compliance with:
- **GDPR**: Data access restrictions and audit trails
- **Quebec Law 25**: Privacy and data protection requirements
- **Healthcare Privacy**: Patient data access controls
- **Odoo Security Best Practices**: Proper ACL and record rule usage

The comprehensive test suite ensures that the mail activity portal access functionality maintains security boundaries while providing the necessary functionality for treatment professionals to manage patient care activities effectively.
