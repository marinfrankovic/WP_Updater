"""WordPress vulnerability lookup via the WPScan API (with aggressive caching).

WPScan's free tier allows only ~25 requests/day, so every lookup is cached per
(kind, slug) in the ``vuln_cache`` table for a configurable TTL (default 24h).
A single scan therefore hits the API at most once per unique plugin/theme/core
version per day, and repeated manual scans are served entirely from cache.

Only enabled when both ``wpscan_enabled`` is set and an API token is present;
otherwise every entry point is a no-op so the rest of the app is unaffected.
"""
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

from . import db

_WPSCAN_BASE = "https://wpscan.com/api/v3"
_PATH = {"plugin": "plugins", "theme": "themes", "wordpress": "wordpresses"}
# Soft cap on API calls per scan run, to stay within the free daily budget.
_RUN_BUDGET = 25


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def enabled() -> bool:
    s = db.get_settings_dict()
    return s.get("wpscan_enabled", "0") == "1" and bool((s.get("wpscan_api_token") or "").strip())


def _token() -> str:
    return (db.get_setting("wpscan_api_token", "") or "").strip()


def _ttl_hours() -> int:
    try:
        return int(db.get_setting("vuln_cache_ttl_hours", "24") or 24)
    except (TypeError, ValueError):
        return 24


def _version_parts(v: Any) -> List[int]:
    return [int(p) for p in re.split(r"[^\d]+", str(v or "")) if p != ""]


def _version_lt(a: Any, b: Any) -> bool:
    """True if version a < version b (numeric, dotted-version comparison)."""
    na, nb = _version_parts(a), _version_parts(b)
    for x, y in zip(na, nb):
        if x != y:
            return x < y
    return len(na) < len(nb)


def _lookup(kind: str, slug: str, budget: Dict[str, int]) -> Optional[List[Dict[str, Any]]]:
    """Return the vulnerability list for one slug, from cache or the API.

    Returns None when the value is unknown (API error / budget exhausted) so the
    caller can distinguish "no known vulns" ([]) from "couldn't check".
    """
    cached = db.get_vuln_cache(kind, slug, _ttl_hours())
    if cached is not None:
        return cached
    if budget["remaining"] <= 0:
        return None
    path = _PATH.get(kind)
    if not path:
        return None
    try:
        resp = requests.get(
            f"{_WPSCAN_BASE}/{path}/{slug}",
            headers={"Authorization": f"Token token={_token()}", "Accept": "application/json"},
            timeout=25,
        )
    except requests.RequestException:
        return None
    budget["remaining"] -= 1

    if resp.status_code == 404:
        db.set_vuln_cache(kind, slug, [])  # unknown to WPScan == no listed vulns
        return []
    if resp.status_code == 429:  # daily budget exhausted upstream
        budget["remaining"] = 0
        return None
    if resp.status_code != 200:
        return None
    try:
        data = resp.json()
    except ValueError:
        return None
    entry: Dict[str, Any] = {}
    if isinstance(data, dict):
        entry = data.get(slug) or (next(iter(data.values())) if len(data) == 1 else {}) or {}
    vulns = entry.get("vulnerabilities") or []
    db.set_vuln_cache(kind, slug, vulns)
    return vulns


def _match(kind: str, name: str, installed: Any, vulns: Optional[List[Dict[str, Any]]],
           slug: str = "") -> List[Dict[str, Any]]:
    """Filter a slug's vulnerabilities to those affecting the installed version."""
    if not vulns:
        return []
    out: List[Dict[str, Any]] = []
    for v in vulns:
        fixed = v.get("fixed_in")
        affected = (not fixed) or (installed and _version_lt(installed, fixed))
        if not affected:
            continue
        refs = v.get("references") or {}
        cves = refs.get("cve") if isinstance(refs, dict) else None
        out.append({
            "type": kind,
            "slug": slug,
            "name": name,
            "installedVersion": installed,
            "title": v.get("title"),
            "fixedIn": fixed,
            "cves": [f"CVE-{c}" if not str(c).upper().startswith("CVE") else c for c in (cves or [])],
        })
    return out


def scan_site(site: Dict[str, Any], scan_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Look up vulnerabilities for a site's installed core/plugins/themes and
    persist the findings. Returns the result dict {checkedAt, count, findings}.
    """
    findings: List[Dict[str, Any]] = []
    budget = {"remaining": _RUN_BUDGET}

    wp = scan_payload.get("wp_version")
    if wp:
        core_slug = re.sub(r"[^\d]", "", str(wp))
        findings += _match("core", "WordPress", wp, _lookup("wordpress", core_slug, budget))

    for p in scan_payload.get("plugins", []) or []:
        file_ = p.get("file") or ""
        slug = file_.split("/")[0] if file_ else (p.get("name") or "")
        if not slug:
            continue
        findings += _match("plugin", p.get("name") or slug, p.get("current"),
                           _lookup("plugin", slug, budget), slug)

    for t in scan_payload.get("themes", []) or []:
        slug = t.get("stylesheet") or t.get("name") or ""
        if not slug:
            continue
        findings += _match("theme", t.get("name") or slug, t.get("current"),
                           _lookup("theme", slug, budget), slug)

    result = {"checkedAt": _now(), "count": len(findings), "findings": findings}
    db.set_setting(f"site_vulns_{site['id']}", json.dumps(result))
    return result


def get_findings(site_id: int) -> Dict[str, Any]:
    raw = db.get_setting(f"site_vulns_{site_id}")
    if not raw:
        return {"checkedAt": None, "count": 0, "findings": []}
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return {"checkedAt": None, "count": 0, "findings": []}
