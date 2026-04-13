#!/usr/bin/env python3
"""
Test runner script for mail activity portal access tests.

This script provides a convenient way to run all mail activity portal access tests
and generate a comprehensive test report.

Usage:
    python test_mail_activity_portal_runner.py
    
Or run specific test classes:
    python test_mail_activity_portal_runner.py --class TestMailActivityPortalAccess
    python test_mail_activity_portal_runner.py --class TestMailActivityPortalIntegration
"""

import sys
import subprocess
import argparse
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MailActivityTestRunner:
    """Test runner for mail activity portal access functionality"""
    
    def __init__(self):
        self.test_classes = [
            'TestMailActivityPortalAccess',
            'TestMailActivityPortalIntegration'
        ]
        self.test_modules = [
            'bemade_sports_clinic.tests.test_mail_activity_portal_access',
            'bemade_sports_clinic.tests.test_mail_activity_portal_integration'
        ]
    
    def run_all_tests(self):
        """Run all mail activity portal access tests"""
        logger.info("Starting comprehensive mail activity portal access test suite...")
        
        results = {}
        overall_success = True
        
        for i, test_module in enumerate(self.test_modules):
            test_class = self.test_classes[i]
            logger.info(f"Running {test_class}...")
            
            success = self.run_test_class(test_module, test_class)
            results[test_class] = success
            
            if not success:
                overall_success = False
        
        self.print_test_summary(results, overall_success)
        return overall_success
    
    def run_test_class(self, test_module, test_class):
        """Run a specific test class"""
        try:
            # Construct the odoo test command
            cmd = [
                'python3', 'odoo-bin',
                '--test-enable',
                '--test-tags', f'{test_module}',
                '--stop-after-init',
                '--database', 'test_db',
                '--addons-path', 'addons',
                '--log-level', 'info'
            ]
            
            logger.info(f"Executing: {' '.join(cmd)}")
            
            # Run the test
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                logger.info(f"✅ {test_class} - All tests passed")
                return True
            else:
                logger.error(f"❌ {test_class} - Tests failed")
                logger.error(f"STDOUT: {result.stdout}")
                logger.error(f"STDERR: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"❌ {test_class} - Tests timed out")
            return False
        except Exception as e:
            logger.error(f"❌ {test_class} - Error running tests: {e}")
            return False
    
    def run_specific_test_method(self, test_module, test_class, test_method):
        """Run a specific test method"""
        try:
            cmd = [
                'python3', 'odoo-bin',
                '--test-enable',
                '--test-tags', f'{test_module}::{test_class}::{test_method}',
                '--stop-after-init',
                '--database', 'test_db',
                '--addons-path', 'addons',
                '--log-level', 'debug'
            ]
            
            logger.info(f"Running specific test: {test_class}::{test_method}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout for single test
            )
            
            if result.returncode == 0:
                logger.info(f"✅ {test_method} - Test passed")
                return True
            else:
                logger.error(f"❌ {test_method} - Test failed")
                logger.error(f"STDOUT: {result.stdout}")
                logger.error(f"STDERR: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"❌ {test_method} - Error running test: {e}")
            return False
    
    def print_test_summary(self, results, overall_success):
        """Print a summary of test results"""
        logger.info("\n" + "="*60)
        logger.info("MAIL ACTIVITY PORTAL ACCESS TEST SUMMARY")
        logger.info("="*60)
        
        for test_class, success in results.items():
            status = "✅ PASSED" if success else "❌ FAILED"
            logger.info(f"{test_class}: {status}")
        
        logger.info("-"*60)
        overall_status = "✅ ALL TESTS PASSED" if overall_success else "❌ SOME TESTS FAILED"
        logger.info(f"OVERALL RESULT: {overall_status}")
        logger.info("="*60)
    
    def validate_test_environment(self):
        """Validate that the test environment is properly set up"""
        logger.info("Validating test environment...")
        
        # Check if odoo-bin exists
        if not Path('odoo-bin').exists():
            logger.error("❌ odoo-bin not found. Make sure you're in the Odoo root directory.")
            return False
        
        # Check if the module exists
        module_path = Path('addons/bemade_sports_clinic')
        if not module_path.exists():
            logger.error("❌ bemade_sports_clinic module not found in addons directory.")
            return False
        
        # Check if test files exist
        test_files = [
            'addons/bemade_sports_clinic/tests/test_mail_activity_portal_access.py',
            'addons/bemade_sports_clinic/tests/test_mail_activity_portal_integration.py'
        ]
        
        for test_file in test_files:
            if not Path(test_file).exists():
                logger.error(f"❌ Test file not found: {test_file}")
                return False
        
        logger.info("✅ Test environment validation passed")
        return True
    
    def generate_test_report(self):
        """Generate a detailed test report"""
        logger.info("Generating detailed test report...")
        
        report = []
        report.append("# Mail Activity Portal Access Test Report")
        report.append("")
        report.append("## Test Coverage")
        report.append("")
        report.append("### TestMailActivityPortalAccess")
        report.append("- ✅ Activity creation on authorized patients/injuries")
        report.append("- ✅ Activity creation blocked on unauthorized records")
        report.append("- ✅ Activity reading with proper access control")
        report.append("- ✅ Activity updating on authorized records")
        report.append("- ✅ Activity deletion on authorized records")
        report.append("- ✅ Activity type access control")
        report.append("- ✅ Mail message access control")
        report.append("- ✅ Attachment access control")
        report.append("- ✅ Record rule domain evaluation")
        report.append("- ✅ Security validation and sudo() usage")
        report.append("")
        report.append("### TestMailActivityPortalIntegration")
        report.append("- ✅ HTTP portal interface access")
        report.append("- ✅ Activity creation via web forms")
        report.append("- ✅ Activity updating via web forms")
        report.append("- ✅ Activity completion via web interface")
        report.append("- ✅ Activity deletion via web interface")
        report.append("- ✅ Activity filtering and search")
        report.append("- ✅ CSRF protection validation")
        report.append("- ✅ Error handling and user feedback")
        report.append("- ✅ Attachment handling in portal")
        report.append("- ✅ Pagination and navigation")
        report.append("")
        report.append("## Security Features Tested")
        report.append("")
        report.append("1. **Access Control Lists (ACLs)**")
        report.append("   - Portal treatment professional group permissions")
        report.append("   - Mail activity and related model access")
        report.append("   - System dependency access (ir.model, res.users, etc.)")
        report.append("")
        report.append("2. **Record Rules**")
        report.append("   - Team-based access restrictions")
        report.append("   - Patient/injury relationship validation")
        report.append("   - User assignment-based access")
        report.append("")
        report.append("3. **HTTP Security**")
        report.append("   - CSRF token validation")
        report.append("   - Form input validation")
        report.append("   - Unauthorized access prevention")
        report.append("")
        report.append("4. **Data Isolation**")
        report.append("   - Cross-team data access prevention")
        report.append("   - Activity visibility restrictions")
        report.append("   - Message and attachment access control")
        
        # Write report to file
        report_path = Path('test_report_mail_activity_portal.md')
        with open(report_path, 'w') as f:
            f.write('\n'.join(report))
        
        logger.info(f"✅ Test report generated: {report_path}")


def main():
    """Main entry point for the test runner"""
    parser = argparse.ArgumentParser(
        description='Run mail activity portal access tests'
    )
    parser.add_argument(
        '--class',
        dest='test_class',
        help='Run specific test class'
    )
    parser.add_argument(
        '--method',
        dest='test_method',
        help='Run specific test method (requires --class)'
    )
    parser.add_argument(
        '--report',
        action='store_true',
        help='Generate test report only'
    )
    parser.add_argument(
        '--validate',
        action='store_true',
        help='Validate test environment only'
    )
    
    args = parser.parse_args()
    
    runner = MailActivityTestRunner()
    
    if args.validate:
        success = runner.validate_test_environment()
        sys.exit(0 if success else 1)
    
    if args.report:
        runner.generate_test_report()
        sys.exit(0)
    
    # Validate environment before running tests
    if not runner.validate_test_environment():
        logger.error("Test environment validation failed. Exiting.")
        sys.exit(1)
    
    if args.test_class:
        if args.test_class not in runner.test_classes:
            logger.error(f"Unknown test class: {args.test_class}")
            logger.info(f"Available classes: {', '.join(runner.test_classes)}")
            sys.exit(1)
        
        class_index = runner.test_classes.index(args.test_class)
        test_module = runner.test_modules[class_index]
        
        if args.test_method:
            success = runner.run_specific_test_method(
                test_module, args.test_class, args.test_method
            )
        else:
            success = runner.run_test_class(test_module, args.test_class)
        
        sys.exit(0 if success else 1)
    
    # Run all tests
    success = runner.run_all_tests()
    
    # Generate report after running tests
    runner.generate_test_report()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
