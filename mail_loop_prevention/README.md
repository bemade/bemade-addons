# Mail Loop Prevention

## Overview

This module prevents communication loops that can occur when two mail servers auto-reply to each other indefinitely. This commonly happens with:

- Delivery receipt acknowledgements
- Out-of-office auto-replies
- Automated notification systems
- Email bounce handlers

## How It Works

The module overrides `mail.thread._message_create()` to detect potential loops by:

1. **Content Hashing**: Creates a hash of message body and subject (unescapes HTML and normalizes whitespace)
2. **Time Window Check**: Looks for identical messages within a configurable time window (default: 48 hours)
3. **Threshold Detection**: Blocks messages if the number of identical messages exceeds a threshold (default: 3)
4. **Smart Filtering**: Only checks automated messages (notification, auto_comment, email types), never blocks user comments

## Configuration

The module uses system parameters that can be configured via Settings > Technical > Parameters > System Parameters:

| Parameter | Default | Valid Range | Description |
|-----------|---------|-------------|-------------|
| `mail_loop_prevention.enabled` | `True` | `True`/`False` | Enable/disable loop prevention |
| `mail_loop_prevention.time_window_hours` | `48` | `1` to `720` | Time window in hours to check for duplicates (max 30 days) |
| `mail_loop_prevention.max_identical_messages` | `3` | `2` to `100` | Maximum identical messages allowed before blocking |

### Configuration Validation

The module validates all configuration parameters when they are set:

- **enabled**: Accepts `True`/`False`, `1`/`0`, `yes`/`no`, `on`/`off` (case-insensitive)
- **time_window_hours**: Must be an integer between 1 and 720 (30 days)
- **max_identical_messages**: Must be an integer between 2 and 100

Invalid values will raise a `ValidationError` and prevent the parameter from being saved.

## Example Scenario

**Without this module:**
```
Server A → Auto-reply to Server B
Server B → Auto-reply to Server A
Server A → Auto-reply to Server B
Server B → Auto-reply to Server A
... (infinite loop)
```

**With this module:**
```
Server A → Auto-reply to Server B (1st message - allowed)
Server B → Auto-reply to Server A (1st message - allowed)
Server A → Auto-reply to Server B (2nd message - allowed)
Server B → Auto-reply to Server A (2nd message - allowed)
Server A → Auto-reply to Server B (3rd message - allowed)
Server B → Auto-reply to Server A (3rd message - allowed)
Server A → Auto-reply to Server B (4th message - BLOCKED)
```

## Technical Details

### Message Types Checked

The module only checks these message types for loops:
- `notification` - System notifications
- `auto_comment` - Automated comments
- `email` - Email messages

Regular `comment` type messages (user posts) are never blocked.

### Duplicate Detection

Messages are considered identical if they have the same:
- Body content (after unescaping HTML entities and normalizing whitespace)
- Subject line

Real-world loops send **exactly the same message** repeatedly, so direct content comparison is sufficient.

### Performance Considerations

- Only checks messages within the configured time window
- Uses SHA-256 hashing for efficient comparison
- Minimal database queries (uses existing message_ids relation)

## Testing

Run the test suite:
```bash
odoo-bin -c odoo.conf -d test_db -i mail_loop_prevention --test-enable --stop-after-init
```

## Troubleshooting

### Legitimate messages being blocked

If legitimate automated messages are being blocked:

1. Check the logs for "Loop prevention: Blocking duplicate message" warnings
2. Increase `mail_loop_prevention.max_identical_messages` threshold
3. Reduce `mail_loop_prevention.time_window_hours` if the messages are spread over time
4. Temporarily disable with `mail_loop_prevention.enabled = False` to diagnose

### Loops still occurring

If loops are still happening:

1. Verify the module is installed and enabled
2. Check that `mail_loop_prevention.enabled = True`
3. Reduce the `max_identical_messages` threshold
4. Check if the messages have varying content (different subjects/bodies)

## License

AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)
