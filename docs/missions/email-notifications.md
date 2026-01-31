# Mission: Email Notifications via Resend

> Living document. Update this, don't create new versions.

## Status: In Progress

## Summary

Branded email notifications from Echo the owl. Black background, neon green/blue accents, playful tone. Supports subject, body, and attachments via CLI and MCP.

## Brand Guidelines

- **Mascot**: Echo the owl
- **Theme**: Dark (#000000) background, neon green (#00ff88) and blue (#00d4ff) accents
- **Tone**: Playful, friendly reminders - not corporate/robotic
- **Sender**: `echo@agentwire.dev`

## User Configuration

In `~/.agentwire/.env`:
```
RESEND_API_KEY=re_xxxxxxxxxxxx
```

In `~/.agentwire/config.yaml`:
```yaml
notifications:
  email:
    from_address: "Echo <echo@agentwire.dev>"
    default_to: "you@example.com"
```

## CLI Usage

```bash
# Simple notification
agentwire email --subject "Task Complete" --body "Your build finished successfully!"

# With attachment
agentwire email --subject "Daily Report" --body "Here's your summary" --attach report.pdf

# Pipe content (markdown supported)
cat summary.md | agentwire email --subject "Briefing"

# Custom recipient
agentwire email --to team@example.com --subject "Deploy Done" --body "v2.1.0 is live"
```

## Email Template Structure

```
┌─────────────────────────────────────────────────┐
│  [Echo owl logo]     AgentWire                  │  <- Header (dark bg)
├─────────────────────────────────────────────────┤
│                                                 │
│  Hey there! 👋                                  │  <- Playful greeting
│                                                 │
│  ┌─────────────────────────────────────────┐   │
│  │  [Subject as heading]                    │   │  <- Content card
│  │                                          │   │
│  │  [Body content - markdown rendered]      │   │
│  │                                          │   │
│  │  📎 attachment.pdf                       │   │  <- Attachments if any
│  └─────────────────────────────────────────┘   │
│                                                 │
│  — Echo 🦉                                      │  <- Sign-off
│                                                 │
├─────────────────────────────────────────────────┤
│  agentwire.dev                                  │  <- Footer
└─────────────────────────────────────────────────┘
```

## Implementation

### Completed

- [x] `resend` and `python-dotenv` dependencies added
- [x] `EmailConfig` and `NotificationsConfig` in config.py
- [x] `RESEND_API_KEY` env var support
- [x] Auto-load `~/.agentwire/.env`
- [x] `agentwire email` command (basic)
- [x] `agentwire/notifications.py` module

### TODO

- [ ] HTML email template with Echo branding
- [ ] Markdown → HTML rendering for body
- [ ] Attachment support (Resend attachments API)
- [ ] Playful greeting variations
- [ ] MCP tool: `agentwire_email()`
- [ ] Task integration: `output.notify: email`
- [ ] Echo owl image asset for emails

### HTML Template

Create `agentwire/templates/email_notification.html`:

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {
      background: #000000;
      color: #e0e0e0;
      font-family: -apple-system, system-ui, sans-serif;
      margin: 0;
      padding: 20px;
    }
    .header {
      text-align: center;
      padding: 20px;
      border-bottom: 1px solid #00ff88;
    }
    .logo { width: 60px; height: 60px; }
    .brand {
      color: #00ff88;
      font-size: 24px;
      font-weight: bold;
    }
    .greeting {
      color: #00d4ff;
      font-size: 18px;
      padding: 20px;
    }
    .content-card {
      background: #111111;
      border: 1px solid #333333;
      border-radius: 8px;
      padding: 20px;
      margin: 20px;
    }
    .subject {
      color: #00ff88;
      font-size: 20px;
      margin-bottom: 15px;
    }
    .body { line-height: 1.6; }
    .attachment {
      color: #00d4ff;
      padding: 10px;
      margin-top: 15px;
      border-top: 1px solid #333;
    }
    .signoff {
      padding: 20px;
      color: #888;
    }
    .footer {
      text-align: center;
      padding: 20px;
      border-top: 1px solid #333;
      color: #666;
    }
    a { color: #00d4ff; }
  </style>
</head>
<body>
  <div class="header">
    <img src="{{ echo_image_url }}" class="logo" alt="Echo">
    <div class="brand">AgentWire</div>
  </div>

  <div class="greeting">{{ greeting }}</div>

  <div class="content-card">
    <div class="subject">{{ subject }}</div>
    <div class="body">{{ body_html }}</div>
    {% if attachments %}
    <div class="attachment">
      📎 {% for a in attachments %}{{ a.filename }}{% if not loop.last %}, {% endif %}{% endfor %}
    </div>
    {% endif %}
  </div>

  <div class="signoff">— Echo 🦉</div>

  <div class="footer">
    <a href="https://agentwire.dev">agentwire.dev</a>
  </div>
</body>
</html>
```

### Greeting Variations

Random selection for playful tone:
- "Hey there! 👋"
- "Psst! Got something for you..."
- "Hoot hoot! 🦉"
- "Quick update for you!"
- "Echo here with news..."

### Resend Attachments

```python
resend.Emails.send({
    "from": "Echo <echo@agentwire.dev>",
    "to": ["user@example.com"],
    "subject": subject,
    "html": rendered_html,
    "attachments": [
        {
            "filename": "report.pdf",
            "content": base64_content,
        }
    ],
})
```

## Testing

1. `agentwire email --subject "Test" --body "Hello from Echo!"`
2. Verify branded HTML email received
3. Test with markdown body
4. Test with attachment
5. Test task integration

## Acceptance Criteria

- [ ] Branded HTML template with Echo
- [ ] Markdown rendering in body
- [ ] Attachment support
- [ ] Greeting variations
- [ ] MCP tool available
- [ ] Task notify integration
- [ ] Works from CLI and agents
