"""Notification channels for AgentWire.

Supports sending branded notifications via email (Resend) and other channels.
"""

import base64
import random
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import resend
from jinja2 import Environment, PackageLoader, select_autoescape

from agentwire.config import get_config


class NotificationError(Exception):
    """Base exception for notification errors."""

    pass


class EmailConfigError(NotificationError):
    """Raised when email configuration is missing or invalid."""

    pass


# Playful greetings from Echo
GREETINGS = [
    "Hey there! 👋",
    "Psst! Got something for you...",
    "Hoot hoot! 🦉",
    "Quick update for you!",
    "Echo here with news...",
    "Hey! Just popping in...",
    "Got a moment? Here's an update!",
    "Fresh from the wire! ⚡",
]


@dataclass
class Attachment:
    """Email attachment."""

    filename: str
    content: bytes  # Raw bytes
    content_type: Optional[str] = None


@dataclass
class EmailResult:
    """Result of sending an email."""

    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None


def _simple_markdown_to_html(text: str) -> str:
    """Convert simple markdown to HTML.

    Handles basic formatting without external dependencies.
    For full markdown support, install 'markdown' package.
    """
    if not text:
        return ""

    lines = text.split("\n")
    html_lines = []
    in_code_block = False
    in_list = False
    list_type = None

    for line in lines:
        # Code blocks
        if line.startswith("```"):
            if in_code_block:
                html_lines.append("</code></pre>")
                in_code_block = False
            else:
                lang = line[3:].strip()
                html_lines.append(f'<pre><code class="language-{lang}">' if lang else "<pre><code>")
                in_code_block = True
            continue

        if in_code_block:
            # Escape HTML in code blocks
            escaped = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            html_lines.append(escaped)
            continue

        # Headers
        if line.startswith("### "):
            html_lines.append(f"<h3>{line[4:]}</h3>")
            continue
        if line.startswith("## "):
            html_lines.append(f"<h2>{line[3:]}</h2>")
            continue
        if line.startswith("# "):
            html_lines.append(f"<h1>{line[2:]}</h1>")
            continue

        # Lists
        if line.startswith("- ") or line.startswith("* "):
            if not in_list or list_type != "ul":
                if in_list:
                    html_lines.append(f"</{list_type}>")
                html_lines.append("<ul>")
                in_list = True
                list_type = "ul"
            html_lines.append(f"<li>{_inline_markdown(line[2:])}</li>")
            continue

        if re.match(r"^\d+\. ", line):
            if not in_list or list_type != "ol":
                if in_list:
                    html_lines.append(f"</{list_type}>")
                html_lines.append("<ol>")
                in_list = True
                list_type = "ol"
            content = re.sub(r"^\d+\. ", "", line)
            html_lines.append(f"<li>{_inline_markdown(content)}</li>")
            continue

        # Close list if we're no longer in one
        if in_list and line.strip():
            html_lines.append(f"</{list_type}>")
            in_list = False
            list_type = None

        # Blockquotes
        if line.startswith("> "):
            html_lines.append(f"<blockquote>{_inline_markdown(line[2:])}</blockquote>")
            continue

        # Empty lines
        if not line.strip():
            if in_list:
                html_lines.append(f"</{list_type}>")
                in_list = False
                list_type = None
            html_lines.append("")
            continue

        # Regular paragraphs
        html_lines.append(f"<p>{_inline_markdown(line)}</p>")

    # Close any open tags
    if in_code_block:
        html_lines.append("</code></pre>")
    if in_list:
        html_lines.append(f"</{list_type}>")

    return "\n".join(html_lines)


def _inline_markdown(text: str) -> str:
    """Convert inline markdown (bold, italic, code, links)."""
    # Escape HTML first
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # Code (backticks) - do this first to avoid processing inside code
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)

    # Bold
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__([^_]+)__", r"<strong>\1</strong>", text)

    # Italic
    text = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)
    text = re.sub(r"_([^_]+)_", r"<em>\1</em>", text)

    # Links
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)

    return text


def _render_email_template(
    subject: str,
    body: str,
    attachments: Optional[list[Attachment]] = None,
    greeting: Optional[str] = None,
    echo_image_url: Optional[str] = None,
    echo_small_url: Optional[str] = None,
    logo_image_url: Optional[str] = None,
) -> str:
    """Render the branded email HTML template.

    Args:
        subject: Email subject (shown as heading in email body)
        body: Email body content (markdown or plain text)
        attachments: List of attachments (for display, not actual sending)
        greeting: Custom greeting (random if not specified)
        echo_image_url: URL to Echo owl image for header
        echo_small_url: URL to small Echo image for sign-off
        logo_image_url: URL to AgentWire text logo

    Returns:
        Rendered HTML string
    """
    env = Environment(
        loader=PackageLoader("agentwire", "templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )

    template = env.get_template("email_notification.html")

    # Convert markdown body to HTML
    body_html = _simple_markdown_to_html(body)

    # Pick random greeting if not specified
    if greeting is None:
        greeting = random.choice(GREETINGS)

    return template.render(
        subject=subject,
        body_html=body_html,
        greeting=greeting,
        attachments=attachments or [],
        echo_image_url=echo_image_url,
        echo_small_url=echo_small_url,
        logo_image_url=logo_image_url,
    )


def send_email(
    to: Optional[str] = None,
    subject: str = "",
    body: str = "",
    attachments: Optional[list[Path | str]] = None,
    from_address: Optional[str] = None,
    greeting: Optional[str] = None,
    plain_text: bool = False,
) -> EmailResult:
    """Send a branded email via Resend.

    Args:
        to: Recipient email address. Uses config default_to if not specified.
        subject: Email subject line.
        body: Email body (markdown supported, converted to HTML).
        attachments: List of file paths to attach.
        from_address: Sender address. Uses config from_address if not specified.
        greeting: Custom greeting. Random if not specified.
        plain_text: If True, send as plain text only (no HTML template).

    Returns:
        EmailResult with success status and message_id or error.

    Raises:
        EmailConfigError: If required configuration is missing.
    """
    config = get_config()
    email_config = config.notifications.email

    # Validate API key
    if not email_config.api_key:
        raise EmailConfigError(
            "Email API key not configured. "
            "Set RESEND_API_KEY in ~/.agentwire/.env "
            "or set notifications.email.api_key in ~/.agentwire/config.yaml"
        )

    # Determine recipient
    recipient = to or email_config.default_to
    if not recipient:
        raise EmailConfigError(
            "No recipient specified and no default_to configured in "
            "notifications.email.default_to"
        )

    # Determine sender
    sender = from_address or email_config.from_address
    if not sender:
        raise EmailConfigError(
            "No sender address configured. "
            "Set notifications.email.from_address in ~/.agentwire/config.yaml"
        )

    # Configure Resend
    resend.api_key = email_config.api_key

    # Process attachments
    attachment_objects: list[Attachment] = []
    resend_attachments = []

    if attachments:
        for attachment_path in attachments:
            path = Path(attachment_path)
            if not path.exists():
                return EmailResult(success=False, error=f"Attachment not found: {path}")

            content = path.read_bytes()
            attachment_objects.append(Attachment(filename=path.name, content=content))

            # Resend wants base64 content as string
            resend_attachments.append({
                "filename": path.name,
                "content": base64.b64encode(content).decode("utf-8"),
            })

    # Build email params
    email_subject = subject or "(no subject)"

    params: dict = {
        "from": sender,
        "to": [recipient],
        "subject": email_subject,
    }

    if plain_text:
        params["text"] = body
    else:
        # Render branded HTML template
        html_content = _render_email_template(
            subject=email_subject,
            body=body,
            attachments=attachment_objects,
            greeting=greeting,
            echo_image_url=email_config.echo_image_url or None,
            echo_small_url=email_config.echo_small_url or None,
            logo_image_url=email_config.logo_image_url or None,
        )
        params["html"] = html_content
        # Also include plain text version
        params["text"] = body

    if resend_attachments:
        params["attachments"] = resend_attachments

    # Send email
    try:
        response = resend.Emails.send(params)
        message_id = response.get("id") if isinstance(response, dict) else str(response)
        return EmailResult(success=True, message_id=message_id)
    except resend.ResendError as e:
        return EmailResult(success=False, error=str(e))
    except Exception as e:
        return EmailResult(success=False, error=f"Unexpected error: {e}")


def cmd_email(args) -> int:
    """CLI handler for email command.

    Sends a branded email notification via Resend.
    """
    # Get body from args or stdin
    body = args.body
    if not body and not sys.stdin.isatty():
        body = sys.stdin.read()

    if not body:
        print("Error: No message body provided. Use --body or pipe content.", file=sys.stderr)
        return 1

    subject = args.subject or "[AgentWire] Notification"

    # Process attachments
    attachments = None
    if hasattr(args, "attach") and args.attach:
        attachments = args.attach if isinstance(args.attach, list) else [args.attach]

    try:
        result = send_email(
            to=args.to,
            subject=subject,
            body=body,
            attachments=attachments,
            plain_text=getattr(args, "plain", False),
        )

        if result.success:
            if not getattr(args, "quiet", False):
                print(f"Email sent (id: {result.message_id})")
            return 0
        else:
            print(f"Error sending email: {result.error}", file=sys.stderr)
            return 1

    except EmailConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
