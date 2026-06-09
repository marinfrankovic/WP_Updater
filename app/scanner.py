"""Connector client + scan orchestration.

Talks to the WP Updater Connector mu-plugin REST API on each site:
  GET  /wp-json/wpupdater/v1/status        -> update status payload
  POST /wp-json/wpupdater/v1/auto-updates  -> enable/disable WP auto-updates
  POST /wp-json/wpupdater/v1/update        -> apply pending updates

For sites still running the pre-rename connector, the client transparently
falls back to the legacy /wp-json/wpmonitor/v1 namespace.
"""
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from . import db
from .config import config

_API_BASE = "/wp-json/wpupdater/v1"
_LEGACY_API_BASE = "/wp-json/wpmonitor/v1"


def _headers(api_key: str) -> Dict[str, str]:
    # Send both the new and legacy key headers so either connector accepts it.
    return {
        "X-WPUpdater-Key": api_key,
        "X-WPMonitor-Key": api_key,
        "Accept": "application/json",
    }


def _endpoint(site_url: str, path: str, base: str = _API_BASE) -> str:
    return f"{site_url.rstrip('/')}{base}{path}"


def fetch_status(site: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], Optional[str]]:
    """Return (ok, payload, error)."""
    bases = [_API_BASE, _LEGACY_API_BASE]
    last_error: Optional[str] = None
    for i, base in enumerate(bases):
        try:
            resp = requests.get(
                _endpoint(site["url"], "/status", base),
                headers=_headers(site["api_key"]),
                timeout=config.REQUEST_TIMEOUT,
                verify=config.VERIFY_TLS,
            )
        except requests.RequestException as exc:
            return False, {}, f"Connection error: {exc}"

        # On the new namespace a 404 means the site still runs the legacy
        # connector; try the legacy namespace before giving up.
        if resp.status_code == 404 and i == 0:
            last_error = "Connector not found (is the mu-plugin installed?)."
            continue
        if resp.status_code == 401:
            return False, {}, "Unauthorized (missing API key)."
        if resp.status_code == 403:
            return False, {}, "Forbidden (invalid API key)."
        if resp.status_code == 404:
            return False, {}, "Connector not found (is the mu-plugin installed?)."
        if resp.status_code != 200:
            return False, {}, f"HTTP {resp.status_code}: {resp.text[:200]}"

        try:
            data = resp.json()
        except ValueError:
            return False, {}, "Invalid JSON response from connector."
        return True, data, None
    return False, {}, last_error or "Connector not reachable."


def set_auto_updates(site: Dict[str, Any], enable: bool) -> Tuple[bool, Optional[str]]:
    for i, base in enumerate([_API_BASE, _LEGACY_API_BASE]):
        try:
            resp = requests.post(
                _endpoint(site["url"], "/auto-updates", base),
                headers=_headers(site["api_key"]),
                data={"enable": "true" if enable else "false"},
                timeout=config.REQUEST_TIMEOUT,
                verify=config.VERIFY_TLS,
            )
        except requests.RequestException as exc:
            return False, f"Connection error: {exc}"
        if resp.status_code == 404 and i == 0:
            continue
        if resp.status_code != 200:
            return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
        return True, None
    return False, "Connector not found."


def apply_updates(site: Dict[str, Any], targets: Optional[List[str]] = None,
                  plugins: Optional[List[str]] = None, themes: Optional[List[str]] = None
                  ) -> Tuple[bool, Dict[str, Any], Optional[str]]:
    payload = {}
    if targets:
        payload["targets"] = ",".join(targets)
    if plugins:
        payload["plugins"] = ",".join(plugins)
    if themes:
        payload["themes"] = ",".join(themes)
    for i, base in enumerate([_API_BASE, _LEGACY_API_BASE]):
        try:
            resp = requests.post(
                _endpoint(site["url"], "/update", base),
                headers=_headers(site["api_key"]),
                data=payload,
                timeout=max(config.REQUEST_TIMEOUT, 180),
                verify=config.VERIFY_TLS,
            )
        except requests.RequestException as exc:
            return False, {}, f"Connection error: {exc}"
        if resp.status_code == 404 and i == 0:
            continue
        if resp.status_code != 200:
            return False, {}, f"HTTP {resp.status_code}: {resp.text[:200]}"
        try:
            return True, resp.json(), None
        except ValueError:
            return False, {}, "Invalid JSON response from connector."
    return False, {}, "Connector not found."


def scan_site(site: Dict[str, Any]) -> Dict[str, Any]:
    """Poll one site, persist the result, and return a summary dict."""
    ok, payload, error = fetch_status(site)
    if ok:
        db.record_scan(site["id"], "ok", payload)
        # Persist the site's WordPress admin email for per-site notifications.
        admin_email = payload.get("admin_email")
        if admin_email:
            db.set_setting(f"site_admin_email_{site['id']}", admin_email)
        # Reconcile desired auto-update state with the site, if it drifted.
        _reconcile_auto_update(site, payload)
    else:
        db.record_scan(site["id"], "error", error=error)
    db.prune_scans(site["id"])
    return {
        "site_id": site["id"],
        "name": site["name"],
        "ok": ok,
        "error": error,
        "counts": payload.get("counts", {}) if ok else {},
    }


def _reconcile_auto_update(site: Dict[str, Any], payload: Dict[str, Any]) -> None:
    """If the dashboard wants auto-updates on for this site but the site reports
    no plugins/themes flagged, push the desired state once."""
    if not site.get("auto_update"):
        return
    plugins = payload.get("plugins", []) or []
    themes = payload.get("themes", []) or []
    any_auto = any(p.get("auto_update") for p in plugins) or any(t.get("auto_update") for t in themes)
    if plugins and not any_auto:
        set_auto_updates(site, True)


def scan_all(enabled_only: bool = True) -> List[Dict[str, Any]]:
    results = []
    for site in db.list_sites(enabled_only=enabled_only):
        results.append(scan_site(site))
        time.sleep(0.2)  # be gentle on shared hosting
    return results
