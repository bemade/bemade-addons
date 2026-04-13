# Customer Account Statement

## Description

This module provides a customer account statement report for Odoo 18. The report displays outstanding invoices for customers, including detailed information about each invoice and totals.

## Features

- Generate account statements for customers showing unpaid and partially paid invoices
- Display invoice details: number, date, due date, PO number, amounts
- Show totals: invoiced amount, paid amount, and outstanding balance
- Available directly from the partner form view (Print menu)
- Multi-currency support

## Usage

1. Navigate to a customer record (Contacts app)
2. Click on the "Print" button
3. Select "Customer Account Statement"
4. The report will generate a PDF showing all outstanding invoices

## Technical Details

- **Model**: `res.partner`
- **Report Type**: QWeb PDF
- **Dependencies**: `account`

## Author

- **Bemade Inc.**
- Website: https://www.bemade.org
- License: LGPL-3

## Version

- **Version**: 18.0.1.0.0
- **Odoo Version**: 18.0
