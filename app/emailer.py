"""SMTP email reporting.

Sends the HTML update report to the dashboard's configured recipients, and
optionally to each site's WordPress admin email (per-site checkbox).
"""
import smtplib
import ssl
from email.message import EmailMessage
from typing import Dict, List, Optional, Tuple

from . import db, reports


def _smtp_config() -> Dict[str, str]:
    s = db.get_settings_dict()
    return {
        "host": s.get("smtp_host", ""),
        "port": int(s.get("smtp_port", "587") or "587"),
        "user": s.get("smtp_user", ""),
        "password": s.get("smtp_password", ""),
        "from": s.get("smtp_from", "") or s.get("smtp_user", ""),
        "tls": s.get("smtp_tls", "1") == "1",
    }


def smtp_ready() -> bool:
    cfg = _smtp_config()
    return bool(cfg["host"] and cfg["from"])


def _send_raw(subject: str, html_body: str, recipients: List[str]) -> Tuple[bool, Optional[str]]:
    recipients = [r.strip() for r in recipients if r and r.strip()]
    if not recipients:
        return False, "No recipients."
    cfg = _smtp_config()
    if not cfg["host"] or not cfg["from"]:
        return False, "SMTP is not configured."

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg["from"]
    msg["To"] = ", ".join(recipients)
    msg.set_content("This report requires an HTML-capable email client.")
    msg.add_alternative(html_body, subtype="html")

    try:
        if cfg["port"] == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=30, context=context) as server:
                if cfg["user"]:
                    server.login(cfg["user"], cfg["password"])
                server.send_message(msg)
        else:
            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=30) as server:
                if cfg["tls"]:
                    server.starttls(context=ssl.create_default_context())
                if cfg["user"]:
                    server.login(cfg["user"], cfg["password"])
                server.send_message(msg)
    except Exception as exc:  # noqa: BLE001 - surface any SMTP failure to the UI
        return False, str(exc)
    return True, None


def send_report(force: bool = False) -> Tuple[bool, str]:
    """Send the global report to dashboard recipients + opted-in site admins.

    Returns (sent, message).
    """
    settings = db.get_settings_dict()
    if settings.get("email_enabled", "0") != "1" and not force:
        return False, "Email reports are disabled."

    only_when_updates = settings.get("email_only_when_updates", "1") == "1"
    if only_when_updates and not force and not reports.has_pending_updates():
        return False, "No pending updates; email skipped."

    html_body = reports.build_html()
    subject = "WordPress Update Report"

    # 1) Dashboard-wide recipients.
    dash_recipients = [r for r in (settings.get("report_recipients", "") or "").split(",") if r.strip()]

    # 2) Per-site admin recipients (only sites with notify_admin enabled). The
    #    address comes from each site's latest connector payload, persisted by
    #    the scanner as setting "site_admin_email_<id>".
    site_admin_recipients = _collect_site_admin_emails()

    all_recipients = list(dict.fromkeys(dash_recipients + site_admin_recipients))
    if not all_recipients:
        return False, "No recipients configured."

    ok, err = _send_raw(subject, html_body, all_recipients)
    if ok:
        return True, f"Report sent to {len(all_recipients)} recipient(s)."
    return False, f"Send failed: {err}"


def _collect_site_admin_emails() -> List[str]:
    """Read each opted-in site's stored admin email from its latest scan payload."""
    emails: List[str] = []
    for site in db.list_sites():
        if not site.get("notify_admin"):
            continue
        email = db.get_setting(f"site_admin_email_{site['id']}")
        if email:
            emails.append(email)
    return emails


def send_test(recipient: str) -> Tuple[bool, Optional[str]]:
    return _send_raw("WP Updater — test email", "<p>This is a test email from WP Updater.</p>", [recipient])


def send_digest(force: bool = False) -> Tuple[bool, str]:
    """Send the weekly digest to the dashboard recipients."""
    settings = db.get_settings_dict()
    if settings.get("digest_enabled", "0") != "1" and not force:
        return False, "Digest is disabled."
    if not smtp_ready():
        return False, "SMTP is not configured."
    recipients = [r for r in (settings.get("report_recipients", "") or "").split(",") if r.strip()]
    if not recipients:
        return False, "No recipients configured."
    html_body = reports.build_digest_html()
    ok, err = _send_raw("WordPress Weekly Digest", html_body, recipients)
    if ok:
        return True, f"Digest sent to {len(recipients)} recipient(s)."
    return False, f"Send failed: {err}"
