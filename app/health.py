"""Post-update site health checks.

After WP Updater applies updates to a site, it fetches the site's public home
page and looks for signs that the update broke the site (HTTP 5xx or a
WordPress "critical error" / database-connection blob). The latest result is
stored per-site so the dashboard can surface a health badge.

Note on rollback: automatic rollback would require a backup mechanism (DB +
files) that the connector does not currently provide, so this module only
*detects and reports* an unhealthy site (and can alert via Telegram). Restoring
is left to the site's own backup tooling.
"""
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import requests

from . import db
from .config import config

# Substrings that indicate a broken WordPress front page.
_CRITICAL_MARKERS = (
    "there has been a critical error",
    "error establishing a database connection",
    "there has been a critical error on this website",
    "fatal error",
    "parse error:",
)

_UA = "Mozilla/5.0 (compatible; WP-Updater-HealthCheck/1.0)"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def enabled() -> bool:
    return db.get_setting("health_check_enabled", "1") == "1"


def check_site(site: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch the site home page and classify its health. Persists + returns the
    result dict: {status, httpStatus, checkedAt, detail}.

    status is one of: healthy | degraded | down | unknown.
    """
    result: Dict[str, Any] = {
        "status": "unknown",
        "httpStatus": None,
        "checkedAt": _now(),
        "detail": None,
    }
    url = site.get("url") or ""
    if not url:
        _store(site["id"], result)
        return result
    try:
        resp = requests.get(
            url,
            timeout=max(config.REQUEST_TIMEOUT, 20),
            verify=config.VERIFY_TLS,
            allow_redirects=True,
            headers={"User-Agent": _UA, "Accept": "text/html"},
        )
    except requests.RequestException as exc:
        result["status"] = "down"
        result["detail"] = f"Unreachable: {exc}"
        _store(site["id"], result)
        return result

    result["httpStatus"] = resp.status_code
    body = (resp.text or "")[:40000].lower()
    marker = next((m for m in _CRITICAL_MARKERS if m in body), None)

    if resp.status_code >= 500:
        result["status"] = "down"
        result["detail"] = f"HTTP {resp.status_code}"
    elif marker:
        result["status"] = "down"
        result["detail"] = "WordPress critical error detected on the home page."
    elif resp.status_code >= 400:
        result["status"] = "degraded"
        result["detail"] = f"HTTP {resp.status_code}"
    else:
        result["status"] = "healthy"
        result["detail"] = f"HTTP {resp.status_code}"

    _store(site["id"], result)
    return result


def _store(site_id: int, result: Dict[str, Any]) -> None:
    db.set_setting(f"site_health_{site_id}", json.dumps(result))


def get_health(site_id: int) -> Optional[Dict[str, Any]]:
    raw = db.get_setting(f"site_health_{site_id}")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None
