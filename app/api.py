"""JSON API consumed by the React SPA.

Maps the SQLite/connector data model onto the contract the frontend expects
(see frontend/src/types/index.ts). All routes are under /api and protected by
the same optional HTTP basic auth as the rest of the dashboard.
"""
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from . import db, emailer, health, scanner, scheduler, telegram, vuln

api = Blueprint("api", __name__, url_prefix="/api")


def _age_days(iso: Optional[str]) -> Optional[int]:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0, int((datetime.now(timezone.utc) - dt).total_seconds() // 86400))


def _clean_error(err: Optional[str]) -> Optional[str]:
    """Turn a raw site error body (often HTML / a WordPress critical-error blob)
    into a short, human-readable line for the activity log."""
    if not err:
        return err
    text = re.sub(r"<[^>]+>", " ", err)          # strip HTML tags
    text = re.sub(r"\s+", " ", text).strip()
    if "critical error" in text.lower():
        return ("The WordPress site hit a critical error while applying the update "
                "(check the site's PHP error log). Often a memory/timeout limit or a "
                "package incompatible with the site's PHP version.")
    return text[:300]


# --------------------------------------------------------------------------- #
# Serialization helpers (DB -> frontend shapes)
# --------------------------------------------------------------------------- #
def _site_status(scan: Optional[Dict[str, Any]]) -> str:
    if scan and scan.get("status") == "error":
        return "failed"
    return "idle"


def _serialize_site(site: Dict[str, Any], scan: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    counts = {
        "core": scan["count_core"] if scan and scan["status"] == "ok" else 0,
        "plugins": scan["count_plugins"] if scan and scan["status"] == "ok" else 0,
        "themes": scan["count_themes"] if scan and scan["status"] == "ok" else 0,
        "total": scan["count_total"] if scan and scan["status"] == "ok" else 0,
    }
    seen = db.get_update_seen_map(site["id"])
    ages = [d for d in (_age_days(v) for v in seen.values()) if d is not None]
    vulns = vuln.get_findings(site["id"])
    return {
        "id": str(site["id"]),
        "name": site["name"],
        "url": site["url"],
        "wordpressVersion": (scan.get("wp_version") if scan else None) or "—",
        "connectorVersion": (scan.get("connector_version") if scan else None) or None,
        "coreUpdateAvailable": counts["core"] > 0,
        "pluginUpdatesCount": counts["plugins"],
        "themeUpdatesCount": counts["themes"],
        "totalUpdates": counts["total"],
        "status": _site_status(scan),
        "lastScanAt": scan.get("scanned_at") if scan else None,
        "lastUpdatedAt": site.get("last_updated_at"),
        "autoUpdate": bool(site.get("auto_update")),
        "notifyAdmin": bool(site.get("notify_admin")),
        "notifyTelegram": bool(site.get("notify_telegram")),
        "group": site.get("grp") or "Ungrouped",
        "selected": False,
        "oldestPendingDays": max(ages) if ages else None,
        "vulnCount": int(vulns.get("count") or 0),
        "health": health.get_health(site["id"]),
    }


def _serialize_updates(site: Dict[str, Any], scan: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not scan or scan.get("status") != "ok":
        return []
    sid = str(site["id"])
    seen = db.get_update_seen_map(site["id"])
    items: List[Dict[str, Any]] = []

    def _age(key: str) -> Dict[str, Any]:
        first = seen.get(key)
        return {"firstSeenAt": first, "ageDays": _age_days(first)}

    core = scan.get("core_update")
    if core:
        items.append({
            "id": f"{sid}-core",
            "siteId": sid,
            "type": "core",
            "slug": "",
            "name": "WordPress",
            "currentVersion": core.get("current") or "—",
            "availableVersion": core.get("available") or "—",
            "status": "available",
            "selected": False,
            **_age("core"),
        })

    for p in scan.get("plugins", []) or []:
        if not p.get("update"):
            continue
        key = p.get("file") or p.get("name")
        items.append({
            "id": f"{sid}-plugin-{p.get('file', p.get('name'))}",
            "siteId": sid,
            "type": "plugin",
            "slug": p.get("file") or p.get("name") or "",
            "name": p.get("name") or p.get("file") or "Plugin",
            "currentVersion": p.get("current") or "—",
            "availableVersion": p.get("available") or "—",
            "status": "available",
            "selected": False,
            **_age(f"plugin:{key}"),
        })

    for t in scan.get("themes", []) or []:
        if not t.get("update"):
            continue
        key = t.get("stylesheet") or t.get("name")
        items.append({
            "id": f"{sid}-theme-{t.get('stylesheet', t.get('name'))}",
            "siteId": sid,
            "type": "theme",
            "slug": t.get("stylesheet") or t.get("name") or "",
            "name": t.get("name") or t.get("stylesheet") or "Theme",
            "currentVersion": t.get("current") or "—",
            "availableVersion": t.get("available") or "—",
            "status": "available",
            "selected": False,
            **_age(f"theme:{key}"),
        })

    return items


def _serialize_activity(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(row["id"]),
        "timestamp": row["created_at"],
        "siteId": str(row["site_id"]) if row.get("site_id") is not None else "",
        "siteName": row["site_name"],
        "action": row["action"],
        "status": row["status"],
        "durationMs": row.get("duration_ms") or 0,
        "error": row.get("error"),
        "details": row.get("details"),
        "resolved": bool(row.get("resolved")),
    }


def _full_state() -> Dict[str, Any]:
    sites = db.list_sites()
    site_payload = []
    update_payload = []
    for site in sites:
        scan = db.latest_scan(site["id"])
        site_payload.append(_serialize_site(site, scan))
        update_payload.extend(_serialize_updates(site, scan))
    activity = [_serialize_activity(a) for a in db.list_activity(limit=100)]
    return {"sites": site_payload, "updates": update_payload, "activity": activity}


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@api.get("/state")
def get_state():
    return jsonify(_full_state())


@api.post("/sites")
def create_site():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    url = (data.get("url") or "").strip()
    api_key = (data.get("apiKey") or "").strip()
    grp = (data.get("group") or "Ungrouped").strip()
    if not (name and url and api_key):
        return jsonify({"error": "name, url and apiKey are required"}), 400
    try:
        site_id = db.add_site(name=name, url=url, api_key=api_key, grp=grp, enabled=True)
    except Exception as exc:  # noqa: BLE001 - duplicate URL etc.
        return jsonify({"error": str(exc)}), 400
    # Immediate first scan so the new row populates.
    site = db.get_site(site_id)
    start = time.time()
    result = scanner.scan_site(site)
    db.record_activity(
        site_id, site["name"], "scan",
        "success" if result["ok"] else "failed",
        duration_ms=int((time.time() - start) * 1000),
        error=None if result["ok"] else result.get("error"),
    )
    return jsonify({"ok": True, "state": _full_state()})


@api.delete("/sites/<int:site_id>")
def remove_site(site_id: int):
    site = db.get_site(site_id)
    if not site:
        return jsonify({"error": "not found"}), 404
    db.delete_site(site_id)
    return jsonify({"ok": True, "state": _full_state()})


@api.patch("/sites/<int:site_id>")
def update_site_info_route(site_id: int):
    site = db.get_site(site_id)
    if not site:
        return jsonify({"error": "not found"}), 404
    data = request.get_json(silent=True) or {}
    fields: Dict[str, Any] = {}
    if "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "name cannot be empty"}), 400
        fields["name"] = name
    if "url" in data:
        url = (data.get("url") or "").strip()
        if not url:
            return jsonify({"error": "url cannot be empty"}), 400
        fields["url"] = url
    if "group" in data:
        fields["grp"] = (data.get("group") or "Ungrouped").strip() or "Ungrouped"
    if "notifyAdmin" in data:
        fields["notify_admin"] = bool(data.get("notifyAdmin"))
    if "notifyTelegram" in data:
        fields["notify_telegram"] = bool(data.get("notifyTelegram"))
    # API key is optional: only change it when a non-empty value is provided.
    api_key = (data.get("apiKey") or "").strip()
    if api_key:
        fields["api_key"] = api_key
    if not fields:
        return jsonify({"error": "nothing to update"}), 400
    try:
        db.update_site(site_id, **fields)
    except Exception as exc:  # noqa: BLE001 - duplicate URL etc.
        return jsonify({"error": str(exc)}), 400
    return jsonify({"ok": True, "state": _full_state()})


@api.post("/sites/<int:site_id>/scan")
def scan_site_route(site_id: int):
    site = db.get_site(site_id)
    if not site:
        return jsonify({"error": "not found"}), 404
    start = time.time()
    result = scanner.scan_site(site)
    db.record_activity(
        site_id, site["name"], "scan",
        "success" if result["ok"] else "failed",
        duration_ms=int((time.time() - start) * 1000),
        error=None if result["ok"] else result.get("error"),
    )
    db.prune_activity()
    return jsonify({"ok": result["ok"], "state": _full_state()})


_SCOPE_TO_TARGETS = {
    "core": ["core"],
    "plugin": ["plugins"],
    "theme": ["themes"],
    "all": None,
}
_SCOPE_TO_ACTION = {
    "core": "update-core",
    "plugin": "update-plugins",
    "theme": "update-themes",
    "all": "update-all",
}


def _collect_details(data: Any) -> tuple[List[Dict[str, Any]], Optional[str]]:
    """Turn one connector /update response into (detail rows, status_error)."""
    details: List[Dict[str, Any]] = []
    applied = (data or {}).get("applied", {}) if isinstance(data, dict) else {}
    if isinstance(applied, dict):
        for group in ("plugins", "themes"):
            for item in (applied.get(group) or []):
                res = "success" if item.get("success", True) else "failed"
                details.append({
                    "name": item.get("name") or item.get("file") or item.get("stylesheet") or group,
                    "result": res,
                    "message": item.get("message") if res == "failed" else None,
                })
        core = applied.get("core")
        if isinstance(core, dict):
            res = "success" if core.get("success") else "failed"
            details.append({
                "name": "WordPress core",
                "result": res,
                "message": core.get("message") if res == "failed" else None,
            })
        for emsg in (applied.get("errors") or []):
            details.append({"name": "error", "result": "failed", "message": emsg})
    status_error = (data or {}).get("status_error") if isinstance(data, dict) else None
    return details, status_error


# When updating "all", run each component in sequence (core, then plugins,
# then themes) rather than one combined call, so each step finishes before the
# next begins.
_ALL_SEQUENCE = ["core", "plugin", "theme"]


def _finalize_update(site: Dict[str, Any], action: str, details: List[Dict[str, Any]],
                     any_ok: bool, first_err: Optional[str],
                     status_error: Optional[str], start: float) -> Dict[str, Any]:
    """Re-scan, compute final status, record one activity entry."""
    duration = int((time.time() - start) * 1000)

    if any_ok:
        rescan = scanner.scan_site(site)
        failed = [d for d in details if d["result"] == "failed"]
        if details and failed:
            status = "partial" if len(failed) < len(details) else "failed"
        else:
            status = "success"
        if not rescan["ok"]:
            status = "partial" if status == "success" else status
        db.touch_last_updated(site["id"])
    else:
        status = "failed"

    if not any_ok:
        error_text = _clean_error(first_err)
    elif status != "success":
        fcount = len([d for d in details if d["result"] == "failed"])
        error_text = f"{fcount} item(s) failed" if fcount else (status_error or "Update incomplete")
    else:
        error_text = None

    db.record_activity(
        site["id"], site["name"], action, status,
        duration_ms=duration,
        error=error_text,
        details=details or None,
    )
    # A successful update clears this site's outstanding error warning on the
    # dashboard tile (the failed entries stay in the activity log, just resolved).
    if status == "success":
        db.resolve_site_failures(site["id"])

    # Post-update health check: if we applied anything, verify the site still
    # loads. A broken site is logged and (best-effort) alerted via Telegram.
    if any_ok and health.enabled():
        try:
            hc = health.check_site(site)
            if hc.get("status") in ("down", "degraded"):
                db.record_activity(
                    site["id"], site["name"], "health-check", "failed",
                    error=f"Post-update health check: {hc.get('detail') or hc.get('status')}",
                )
                try:
                    telegram.send_message(
                        db.get_setting("telegram_chat_id", "") or "",
                        f"⚠️ <b>{site['name']}</b> looks unhealthy after an update: "
                        f"{hc.get('detail') or hc.get('status')}",
                    )
                except Exception:  # noqa: BLE001
                    pass
        except Exception:  # noqa: BLE001 - health check must never break an update
            pass

    return {"ok": any_ok, "status": status, "error": first_err}


def _run_update(site: Dict[str, Any], scope: str) -> Dict[str, Any]:
    action = _SCOPE_TO_ACTION.get(scope, "update-all")
    steps = _ALL_SEQUENCE if scope == "all" else [scope]

    start = time.time()
    details: List[Dict[str, Any]] = []
    status_error: Optional[str] = None
    any_ok = False
    first_err: Optional[str] = None

    for step in steps:
        targets = _SCOPE_TO_TARGETS.get(step, None)
        ok, data, err = scanner.apply_updates(site, targets)
        if ok:
            any_ok = True
            step_details, step_status_error = _collect_details(data)
            details.extend(step_details)
            status_error = status_error or step_status_error
        else:
            first_err = first_err or err
            details.append({
                "name": f"{step} update",
                "result": "failed",
                "message": _clean_error(err),
            })

    return _finalize_update(site, action, details, any_ok, first_err, status_error, start)


def _run_item_update(site: Dict[str, Any], item_type: str, slug: str) -> Dict[str, Any]:
    """Update a single plugin/theme (by slug) or core."""
    start = time.time()
    if item_type == "core":
        action = "update-core"
        ok, data, err = scanner.apply_updates(site, targets=["core"])
    elif item_type == "plugin":
        action = "update-plugins"
        ok, data, err = scanner.apply_updates(site, plugins=[slug])
    else:
        action = "update-themes"
        ok, data, err = scanner.apply_updates(site, themes=[slug])

    details: List[Dict[str, Any]] = []
    status_error: Optional[str] = None
    first_err: Optional[str] = None
    if ok:
        details, status_error = _collect_details(data)
    else:
        first_err = err
        details.append({
            "name": f"{item_type} update",
            "result": "failed",
            "message": _clean_error(err),
        })

    return _finalize_update(site, action, details, ok, first_err, status_error, start)


@api.post("/sites/<int:site_id>/update")
def update_site_route(site_id: int):
    site = db.get_site(site_id)
    if not site:
        return jsonify({"error": "not found"}), 404
    scope = (request.get_json(silent=True) or {}).get("scope", "all")
    _run_update(site, scope)
    db.prune_activity()
    return jsonify({"ok": True, "state": _full_state()})


@api.post("/sites/<int:site_id>/update-item")
def update_item_route(site_id: int):
    site = db.get_site(site_id)
    if not site:
        return jsonify({"error": "not found"}), 404
    data = request.get_json(silent=True) or {}
    item_type = data.get("type")
    slug = (data.get("slug") or "").strip()
    if item_type not in ("plugin", "theme", "core"):
        return jsonify({"error": "type must be plugin, theme or core"}), 400
    if item_type != "core" and not slug:
        return jsonify({"error": "slug is required"}), 400
    _run_item_update(site, item_type, slug)
    db.prune_activity()
    return jsonify({"ok": True, "state": _full_state()})


@api.post("/sites/<int:site_id>/auto-update")
def set_auto_update_route(site_id: int):
    site = db.get_site(site_id)
    if not site:
        return jsonify({"error": "not found"}), 404
    enabled = bool((request.get_json(silent=True) or {}).get("enabled"))
    ok, error = scanner.set_auto_updates(site, enabled)
    if not ok:
        return jsonify({"error": _clean_error(error) or "Failed to set auto-update"}), 502
    db.update_site(site_id, auto_update=enabled)
    return jsonify({"ok": True, "state": _full_state()})


@api.post("/activity/<int:entry_id>/resolve")
def resolve_activity_route(entry_id: int):
    db.resolve_activity(entry_id)
    return jsonify({"ok": True, "state": _full_state()})


@api.post("/scan-all")
def scan_all_route():
    for site in db.list_sites(enabled_only=True):
        start = time.time()
        result = scanner.scan_site(site)
        db.record_activity(
            site["id"], site["name"], "scan",
            "success" if result["ok"] else "failed",
            duration_ms=int((time.time() - start) * 1000),
            error=None if result["ok"] else result.get("error"),
        )
    db.prune_activity()
    # A manual "Scan all" now also sends the configured reports (respecting the
    # enabled / only-when-updates settings), so updates released between the
    # scheduled scans still trigger a notification when you refresh.
    try:
        emailer.send_report(force=False)
    except Exception:  # noqa: BLE001 - never let a notifier fail the request
        pass
    try:
        telegram.send_report(force=False)
    except Exception:  # noqa: BLE001
        pass
    return jsonify({"ok": True, "state": _full_state()})


@api.post("/bulk-update")
def bulk_update_route():
    data = request.get_json(silent=True) or {}
    site_ids = data.get("siteIds") or []
    scope = data.get("scope", "all")
    for raw_id in site_ids:
        try:
            site = db.get_site(int(raw_id))
        except (TypeError, ValueError):
            site = None
        if site:
            _run_update(site, scope)
    db.prune_activity()
    return jsonify({"ok": True, "state": _full_state()})


# --------------------------------------------------------------------------- #
# Scan schedule
# --------------------------------------------------------------------------- #
def _schedule_payload() -> Dict[str, Any]:
    settings = db.get_settings_dict()
    status = scheduler.status()
    try:
        hour = int(settings.get("scan_hour", "6") or 6)
    except (TypeError, ValueError):
        hour = 6
    try:
        minute = int(settings.get("scan_minute", "0") or 0)
    except (TypeError, ValueError):
        minute = 0
    cron = scheduler._effective_cron(settings)
    # Keep the legacy hour/minute fields in sync with the effective cron when it
    # is a simple "every day at HH:MM" expression, so older clients still work.
    parts = cron.split()
    if len(parts) == 5 and parts[1].isdigit() and parts[0].isdigit() \
            and parts[2] == "*" and parts[3] == "*" and parts[4] == "*":
        minute = max(0, min(59, int(parts[0])))
        hour = max(0, min(23, int(parts[1])))
    return {
        "enabled": settings.get("scan_enabled", "1") == "1",
        "hour": max(0, min(23, hour)),
        "minute": max(0, min(59, minute)),
        "cron": cron,
        "description": scheduler.describe_cron(cron),
        "nextRun": status.get("next_run"),
        "lastRun": status.get("last_run"),
    }


@api.get("/schedule")
def get_schedule_route():
    return jsonify(_schedule_payload())


@api.post("/schedule")
def set_schedule_route():
    data = request.get_json(silent=True) or {}

    if "enabled" in data:
        db.set_setting("scan_enabled", "1" if data.get("enabled") else "0")

    # Preferred: a full cron expression (built by the UI or supplied directly).
    if "cron" in data and data["cron"] is not None:
        cron = str(data["cron"]).strip()
        ok, err = scheduler.validate_cron(cron)
        if not ok:
            return jsonify({"error": f"Invalid cron expression: {err}"}), 400
        db.set_setting("scan_cron", cron)
        # Mirror simple daily expressions back into the legacy fields.
        parts = cron.split()
        if len(parts) == 5 and parts[0].isdigit() and parts[1].isdigit() \
                and parts[2] == "*" and parts[3] == "*" and parts[4] == "*":
            db.set_setting("scan_minute", str(int(parts[0])))
            db.set_setting("scan_hour", str(int(parts[1])))

    # Legacy: discrete hour/minute (kept for backward compatibility). When no
    # cron is supplied, build a daily expression from these so the engine and
    # the GUI stay consistent.
    elif "hour" in data or "minute" in data:
        hour = None
        minute = None
        if "hour" in data:
            try:
                hour = int(data["hour"])
            except (TypeError, ValueError):
                return jsonify({"error": "hour must be a number 0-23"}), 400
            if not 0 <= hour <= 23:
                return jsonify({"error": "hour must be between 0 and 23"}), 400
            db.set_setting("scan_hour", str(hour))
        if "minute" in data:
            try:
                minute = int(data["minute"])
            except (TypeError, ValueError):
                return jsonify({"error": "minute must be a number 0-59"}), 400
            if not 0 <= minute <= 59:
                return jsonify({"error": "minute must be between 0 and 59"}), 400
            db.set_setting("scan_minute", str(minute))
        s = db.get_settings_dict()
        h = hour if hour is not None else int(s.get("scan_hour", "6") or 6)
        m = minute if minute is not None else int(s.get("scan_minute", "0") or 0)
        db.set_setting("scan_cron", f"{m} {h} * * *")

    # Wake the scheduler so the new schedule takes effect immediately.
    scheduler.request_reschedule()
    return jsonify({"ok": True, "schedule": _schedule_payload()})



# --------------------------------------------------------------------------- #
# Email / SMTP settings
# --------------------------------------------------------------------------- #
def _email_payload() -> Dict[str, Any]:
    s = db.get_settings_dict()
    try:
        port = int(s.get("smtp_port", "587") or 587)
    except (TypeError, ValueError):
        port = 587
    return {
        "enabled": s.get("email_enabled", "0") == "1",
        "host": s.get("smtp_host", "") or "",
        "port": port,
        "user": s.get("smtp_user", "") or "",
        "from": s.get("smtp_from", "") or "",
        "tls": s.get("smtp_tls", "1") == "1",
        "recipients": s.get("report_recipients", "") or "",
        "onlyWhenUpdates": s.get("email_only_when_updates", "1") == "1",
        # Never expose the stored password; only whether one is set.
        "passwordSet": bool(s.get("smtp_password")),
    }


@api.get("/email")
def get_email_route():
    return jsonify(_email_payload())


@api.post("/email")
def set_email_route():
    data = request.get_json(silent=True) or {}

    if "enabled" in data:
        db.set_setting("email_enabled", "1" if data.get("enabled") else "0")
    if "onlyWhenUpdates" in data:
        db.set_setting("email_only_when_updates", "1" if data.get("onlyWhenUpdates") else "0")
    if "tls" in data:
        db.set_setting("smtp_tls", "1" if data.get("tls") else "0")
    if "host" in data:
        db.set_setting("smtp_host", (data.get("host") or "").strip())
    if "user" in data:
        db.set_setting("smtp_user", (data.get("user") or "").strip())
    if "from" in data:
        db.set_setting("smtp_from", (data.get("from") or "").strip())
    if "recipients" in data:
        recipients = ",".join(
            r.strip() for r in (data.get("recipients") or "").split(",") if r.strip()
        )
        db.set_setting("report_recipients", recipients)
    if "port" in data:
        try:
            port = int(data["port"])
        except (TypeError, ValueError):
            return jsonify({"error": "port must be a number"}), 400
        if not 1 <= port <= 65535:
            return jsonify({"error": "port must be between 1 and 65535"}), 400
        db.set_setting("smtp_port", str(port))
    # Password is write-only: only overwrite when a non-empty value is supplied.
    password = data.get("password")
    if isinstance(password, str) and password.strip():
        db.set_setting("smtp_password", password)

    return jsonify({"ok": True, "email": _email_payload()})


@api.post("/email/test")
def test_email_route():
    data = request.get_json(silent=True) or {}
    recipient = (data.get("recipient") or "").strip()
    if not recipient:
        return jsonify({"error": "recipient is required"}), 400
    ok, err = emailer.send_test(recipient)
    if not ok:
        return jsonify({"error": err or "Send failed"}), 502
    return jsonify({"ok": True, "message": f"Test email sent to {recipient}."})


# --------------------------------------------------------------------------- #
# Telegram notifications
# --------------------------------------------------------------------------- #
def _telegram_payload() -> Dict[str, Any]:
    s = db.get_settings_dict()
    return {
        "enabled": s.get("telegram_enabled", "0") == "1",
        "chatId": s.get("telegram_chat_id", "") or "",
        "onlyWhenUpdates": s.get("telegram_only_when_updates", "1") == "1",
        # Never expose the stored bot token; only whether one is set.
        "tokenSet": bool(s.get("telegram_bot_token")),
    }


@api.get("/notifications")
def get_notifications_route():
    return jsonify(_telegram_payload())


@api.post("/notifications")
def set_notifications_route():
    data = request.get_json(silent=True) or {}

    if "enabled" in data:
        db.set_setting("telegram_enabled", "1" if data.get("enabled") else "0")
    if "onlyWhenUpdates" in data:
        db.set_setting("telegram_only_when_updates", "1" if data.get("onlyWhenUpdates") else "0")
    if "chatId" in data:
        db.set_setting("telegram_chat_id", (data.get("chatId") or "").strip())
    # Token is write-only: only overwrite when a non-empty value is supplied.
    token = data.get("token")
    if isinstance(token, str) and token.strip():
        db.set_setting("telegram_bot_token", token.strip())

    return jsonify({"ok": True, "notifications": _telegram_payload()})


@api.post("/notifications/test")
def test_notifications_route():
    data = request.get_json(silent=True) or {}
    # Allow an inline chat id / token override so the user can test before saving.
    chat_id = (data.get("chatId") or db.get_setting("telegram_chat_id", "") or "").strip()
    token = (data.get("token") or "").strip() or None
    if not chat_id:
        return jsonify({"error": "chatId is required"}), 400
    ok, err = telegram.send_test(chat_id, token=token)
    if not ok:
        return jsonify({"error": err or "Send failed"}), 502
    return jsonify({"ok": True, "message": "Test message sent."})


# --------------------------------------------------------------------------- #
# Security — vulnerability scanning (WPScan)
# --------------------------------------------------------------------------- #
def _security_payload() -> Dict[str, Any]:
    s = db.get_settings_dict()
    try:
        ttl = int(s.get("vuln_cache_ttl_hours", "24") or 24)
    except (TypeError, ValueError):
        ttl = 24
    return {
        "enabled": s.get("wpscan_enabled", "0") == "1",
        "cacheTtlHours": ttl,
        # Never expose the stored token; only whether one is set.
        "tokenSet": bool((s.get("wpscan_api_token") or "").strip()),
    }


@api.get("/security")
def get_security_route():
    return jsonify(_security_payload())


@api.post("/security")
def set_security_route():
    data = request.get_json(silent=True) or {}
    if "enabled" in data:
        db.set_setting("wpscan_enabled", "1" if data.get("enabled") else "0")
    if "cacheTtlHours" in data:
        try:
            ttl = int(data["cacheTtlHours"])
        except (TypeError, ValueError):
            return jsonify({"error": "cacheTtlHours must be a number"}), 400
        db.set_setting("vuln_cache_ttl_hours", str(max(1, min(720, ttl))))
    # Token is write-only: only overwrite when a non-empty value is supplied.
    token = data.get("token")
    if isinstance(token, str) and token.strip():
        db.set_setting("wpscan_api_token", token.strip())
    return jsonify({"ok": True, "security": _security_payload()})


@api.post("/vulns/scan")
def scan_vulns_route():
    if not vuln.enabled():
        return jsonify({"error": "Vulnerability scanning is not enabled (add a WPScan API token)."}), 400
    for site in db.list_sites(enabled_only=True):
        scan = db.latest_scan(site["id"])
        if not scan or scan.get("status") != "ok":
            continue
        payload = {
            "wp_version": scan.get("wp_version"),
            "plugins": scan.get("plugins", []),
            "themes": scan.get("themes", []),
        }
        try:
            vuln.scan_site(site, payload)
        except Exception:  # noqa: BLE001 - one site's failure must not abort the run
            pass
    return jsonify({"ok": True, "state": _full_state()})


@api.get("/vulns")
def get_vulns_route():
    out = []
    for site in db.list_sites():
        findings = vuln.get_findings(site["id"])
        out.append({
            "siteId": str(site["id"]),
            "siteName": site["name"],
            "checkedAt": findings.get("checkedAt"),
            "count": int(findings.get("count") or 0),
            "findings": findings.get("findings") or [],
        })
    return jsonify({"sites": out})


@api.post("/sites/<int:site_id>/health")
def health_check_route(site_id: int):
    site = db.get_site(site_id)
    if not site:
        return jsonify({"error": "not found"}), 404
    health.check_site(site)
    return jsonify({"ok": True, "state": _full_state()})


# --------------------------------------------------------------------------- #
# Weekly digest
# --------------------------------------------------------------------------- #
def _digest_payload() -> Dict[str, Any]:
    s = db.get_settings_dict()
    cron = (s.get("digest_cron") or "0 8 * * 1").strip()
    return {
        "enabled": s.get("digest_enabled", "0") == "1",
        "cron": cron,
        "description": scheduler.describe_cron(cron),
        "channels": s.get("digest_channels", "email,telegram") or "",
    }


@api.get("/digest")
def get_digest_route():
    return jsonify(_digest_payload())


@api.post("/digest")
def set_digest_route():
    data = request.get_json(silent=True) or {}
    if "enabled" in data:
        db.set_setting("digest_enabled", "1" if data.get("enabled") else "0")
    if "cron" in data and data["cron"] is not None:
        cron = str(data["cron"]).strip()
        ok, err = scheduler.validate_cron(cron)
        if not ok:
            return jsonify({"error": f"Invalid cron expression: {err}"}), 400
        db.set_setting("digest_cron", cron)
    if "channels" in data:
        raw = data.get("channels")
        if isinstance(raw, list):
            chans = [str(c).strip() for c in raw]
        else:
            chans = [c.strip() for c in str(raw or "").split(",")]
        chans = [c for c in chans if c in ("email", "telegram")]
        db.set_setting("digest_channels", ",".join(dict.fromkeys(chans)))
    scheduler.request_reschedule()
    return jsonify({"ok": True, "digest": _digest_payload()})


@api.post("/digest/test")
def test_digest_route():
    scheduler.send_digest()
    return jsonify({"ok": True, "message": "Digest sent (if a channel is configured)."})

