"""Telegram notification reporting.

Sends a short update summary to a configured Telegram chat via the Bot API.
Mirrors emailer.py and uses only the stdlib (urllib) — no extra dependencies.
The destination host is always api.telegram.org (no user-supplied URL), so
there is no SSRF surface; only the bot token and chat id are configurable.
"""
import json
import urllib.error
import urllib.parse
import urllib.request
from html import escape
from typing import Dict, List, Optional, Tuple

from . import db

_API_BASE = "https://api.telegram.org"
_MAX_LEN = 4096  # Telegram hard limit per message.


def _config() -> Dict[str, str]:
    s = db.get_settings_dict()
    return {
        "token": s.get("telegram_bot_token", ""),
        "chat_id": s.get("telegram_chat_id", ""),
    }


def telegram_ready() -> bool:
    cfg = _config()
    return bool(cfg["token"] and cfg["chat_id"])


def send_message(chat_id: str, text: str, token: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """POST a single HTML message to the Telegram Bot API."""
    cfg = _config()
    token = (token or cfg["token"] or "").strip()
    chat_id = (chat_id or "").strip()
    if not token or not chat_id:
        return False, "Telegram is not configured."
    if len(text) > _MAX_LEN:
        text = text[: _MAX_LEN - 1] + "…"
    url = f"{_API_BASE}/bot{token}/sendMessage"
    payload = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - fixed api.telegram.org host
            body = json.loads(resp.read().decode("utf-8", "replace"))
        if not body.get("ok"):
            return False, body.get("description") or "Telegram API error."
        return True, None
    except urllib.error.HTTPError as exc:  # surface Telegram's error description
        try:
            detail = json.loads(exc.read().decode("utf-8", "replace")).get("description")
        except Exception:  # noqa: BLE001
            detail = None
        return False, detail or f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001 - surface any failure to the UI
        return False, str(exc)


def _included_sites() -> List[Dict]:
    """Sites to include in the Telegram summary: those flagged notify_telegram,
    or all sites when none are flagged (so a single global chat still works)."""
    sites = db.list_sites()
    flagged = [s for s in sites if s.get("notify_telegram")]
    return flagged or sites


def _build_summary(sites: Optional[List[Dict]] = None) -> Tuple[str, int]:
    """Compose a single HTML summary of pending updates across the given sites.

    Returns (message_text, total_pending_updates). Every selected site is folded
    into one message — never one message per site.
    """
    if sites is None:
        sites = _included_sites()
    total_sites = len(sites)
    core = plugins = themes = errors = 0
    pending_lines: List[str] = []
    for site in sites:
        scan = db.latest_scan(site["id"])
        if not scan:
            continue
        if scan["status"] != "ok":
            errors += 1
            continue
        core += scan["count_core"]
        plugins += scan["count_plugins"]
        themes += scan["count_themes"]
        if scan["count_total"] > 0:
            pending_lines.append(
                f"• <b>{escape(site['name'])}</b>: {scan['count_total']} "
                f"(core {scan['count_core']}, plugins {scan['count_plugins']}, themes {scan['count_themes']})"
            )
    total = core + plugins + themes
    header = (
        "<b>WordPress Update Report</b>\n"
        f"Sites: {total_sites} · Pending: {total} "
        f"(core {core}, plugins {plugins}, themes {themes})"
    )
    if errors:
        header += f" · Errors: {errors}"
    if pending_lines:
        return header + "\n\n" + "\n".join(pending_lines), total
    return header + "\n\nNo pending updates. 🎉", total


def send_report(force: bool = False) -> Tuple[bool, str]:
    """Send ONE cumulative update summary to the configured chat.

    All selected sites are combined into a single message. Returns (sent, msg).
    """
    settings = db.get_settings_dict()
    if settings.get("telegram_enabled", "0") != "1" and not force:
        return False, "Telegram reports are disabled."
    if not telegram_ready():
        return False, "Telegram is not configured."
    text, pending = _build_summary(_included_sites())
    only_when_updates = settings.get("telegram_only_when_updates", "1") == "1"
    if only_when_updates and not force and pending == 0:
        return False, "No pending updates; Telegram message skipped."
    cfg = _config()
    ok, err = send_message(cfg["chat_id"], text)
    if ok:
        return True, "Telegram report sent."
    return False, f"Telegram send failed: {err}"


def send_test(chat_id: str, token: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    return send_message(chat_id, "✅ Test message from WP Updater.", token=token)


def send_digest(force: bool = False) -> Tuple[bool, str]:
    """Send the weekly digest summary to the configured chat."""
    from . import reports  # local import keeps module load order simple
    settings = db.get_settings_dict()
    if settings.get("digest_enabled", "0") != "1" and not force:
        return False, "Digest is disabled."
    if not telegram_ready():
        return False, "Telegram is not configured."
    text = reports.build_digest_text()
    cfg = _config()
    ok, err = send_message(cfg["chat_id"], text)
    if ok:
        return True, "Digest sent."
    return False, f"Telegram send failed: {err}"
