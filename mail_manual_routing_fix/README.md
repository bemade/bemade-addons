# Lost Messages Routing - Bug Fixes

Fixes critical bugs in `mail_manual_routing` (faOtools) module.

## Bug Fixes

### 1. HTML Escaping

**Problem**: The original module escapes all message bodies with `escape()`, breaking HTML emails.

**Fix**: Respects the `body_is_html` flag:
- HTML body → preserved with `Markup()`
- Plain text → converted properly with `plaintext2html()`

### 2. Threading Preservation

**Problem**: When attaching messages, the original wizard loses threading metadata because:
1. `In-Reply-To` and `References` headers are not stored on `mail.message`
2. The wizard uses raw SQL that doesn't set `parent_id`

**Fix**:
- Store headers in `lost_in_reply_to` and `lost_references` fields during lost message creation
- When routing, find parent message using these headers
- Set `parent_id` to maintain conversation threading

### 3. Origin Tracking

- `lost_origin` - Boolean flag to identify routed messages
- `write_date` / `write_uid` - Standard fields provide when/who routed

## New Fields on mail.message

| Field | Type | Description |
|-------|------|-------------|
| `lost_in_reply_to` | Char | Original In-Reply-To header |
| `lost_references` | Text | Original References header |
| `lost_origin` | Boolean | From Lost Messages |

## Installation

1. Requires `mail_manual_routing` (faOtools)
2. Install this module
3. Update database

## License

LGPL-3

## Author

Bemade Inc.
