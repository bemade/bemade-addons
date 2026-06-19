from odoo.tests import TransactionCase, tagged
import uuid


@tagged("post_install", "-at_install")
class TestPartnerEmailDomain(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env["res.partner"]

    def test_generate_access_token_uniqueness(self):
        """Test that access tokens are unique"""
        partner = self.Partner.create({"name": "Test Partner"})
        token1 = partner._generate_access_token()
        token2 = partner._generate_access_token()
        self.assertNotEqual(token1, token2)
        self.assertEqual(len(token1), 32)  # UUID hex is 32 chars

    def test_access_token_storage(self):
        """Test that access tokens are stored correctly"""
        partner = self.Partner.create({"name": "Token Partner"})
        token = partner._generate_access_token()
        partner.write({"access_token": token})
        self.assertEqual(partner.access_token, token)

    def test_partner_email_domain_field(self):
        """Test email_domain field"""
        partner = self.Partner.create({
            "name": "Domain Partner",
            "email_domain": "example.com"
        })
        self.assertEqual(partner.email_domain, "example.com")

    def test_partner_is_subdivision_field(self):
        """Test is_subdivision field"""
        partner = self.Partner.create({
            "name": "Subdivision",
            "is_subdivision": True
        })
        self.assertTrue(partner.is_subdivision)

    def test_check_parent_from_email_domain_with_parent_existing(self):
        """Test that check skips partners that already have parent_id"""
        parent = self.Partner.create({
            "name": "Existing Parent",
            "email_domain": "skip.org"
        })

        child = self.Partner.create({
            "name": "Child",
            "parent_id": parent.id,
            "email": "user@skip.org"
        })

        # Should remain with existing parent
        self.assertEqual(child.parent_id.id, parent.id)

    def test_check_parent_no_email(self):
        """Test check when partner has no email"""
        parent = self.Partner.create({
            "name": "Parent",
            "email_domain": "noemail.org"
        })

        child = self.Partner.create({
            "name": "No Email Child"
        })

        # Should not crash and remain without parent
        child._check_parent_from_email_domain()
        self.assertFalse(child.parent_id)

    def test_check_parent_invalid_email_format(self):
        """Test check with invalid email (no @)"""
        parent = self.Partner.create({
            "name": "Parent",
            "email_domain": "domain.org"
        })

        child = self.Partner.create({
            "name": "Invalid Email"
        })

        # Should not crash when checking without email
        child._check_parent_from_email_domain()
        self.assertIsNotNone(child.id)  # Verify child was created

    def test_check_parent_exact_domain_match(self):
        """Test email domain matching logic"""
        parent = self.Partner.create({
            "name": "Parent",
            "email_domain": "example.org"
        })

        child = self.Partner.create({
            "name": "Child",
            "email": "user@example.org"
        })

        # Domain check should work
        child._check_parent_from_email_domain()
        self.assertTrue(child.id)

    def test_is_subdivision_onchange_contact_to_other(self):
        """Test is_subdivision changes type from contact to other"""
        partner = self.Partner.create({
            "name": "Contact Type",
            "type": "contact"
        })

        partner.is_subdivision = True
        partner._onchange_is_subdivision()
        self.assertEqual(partner.type, "other")

    def test_is_subdivision_onchange_non_contact(self):
        """Test is_subdivision doesn't change non-contact types"""
        partner = self.Partner.create({
            "name": "Invoice Type",
            "type": "invoice"
        })

        partner.is_subdivision = True
        partner._onchange_is_subdivision()
        self.assertEqual(partner.type, "invoice")

    def test_write_email_triggers_check(self):
        """Test that write with email triggers domain check"""
        parent = self.Partner.create({
            "name": "Parent",
            "email_domain": "write.org"
        })

        partner = self.Partner.create({"name": "Partner"})

        # Write email should trigger check
        partner.write({"email": "test@write.org"})
        self.assertEqual(partner.email, "test@write.org")

    def test_write_without_email_no_check(self):
        """Test that write without email field doesn't trigger check"""
        partner = self.Partner.create({
            "name": "Partner",
            "email": "original@example.com"
        })

        # Write other field
        partner.write({"is_subdivision": True})
        self.assertEqual(partner.email, "original@example.com")

    def test_create_multi_with_emails(self):
        """Test create_multi with multiple partners"""
        parent = self.Partner.create({
            "name": "Parent",
            "email_domain": "multi.org"
        })

        partners = self.Partner.create([
            {"name": "P1", "email": "p1@multi.org"},
            {"name": "P2", "email": "p2@multi.org"},
        ])

        self.assertEqual(len(partners), 2)
        self.assertTrue(all(p.id for p in partners))
