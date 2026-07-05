"""HTML / Markdown report generation from the latest scan per site."""
import os
from datetime import datetime, timezone
from html import escape
from typing import Any, Dict, List, Optional, Tuple

from . import db
from .config import config


def _gather() -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Return (rows, totals) where each row is a site + its latest scan."""
    rows = []
    totals = {"sites": 0, "core": 0, "plugins": 0, "themes": 0, "total": 0, "errors": 0}
    for site in db.list_sites():
        scan = db.latest_scan(site["id"])
        rows.append({"site": site, "scan": scan})
        totals["sites"] += 1
        if not scan:
            continue
        if scan["status"] != "ok":
            totals["errors"] += 1
            continue
        totals["core"] += scan["count_core"]
        totals["plugins"] += scan["count_plugins"]
        totals["themes"] += scan["count_themes"]
        totals["total"] += scan["count_total"]
    return rows, totals


def build_markdown() -> str:
    rows, totals = _gather()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# WordPress Update Report — {now}",
        "",
        f"- Sites monitored: **{totals['sites']}**",
        f"- Pending updates: **{totals['total']}** "
        f"(core {totals['core']}, plugins {totals['plugins']}, themes {totals['themes']})",
        f"- Sites with errors: **{totals['errors']}**",
        "",
        "| Site | WP | PHP | Core | Plugins | Themes | Auto-update | Status |",
        "|------|----|----|------|---------|--------|-------------|--------|",
    ]
    for row in rows:
        site, scan = row["site"], row["scan"]
        auto = "yes" if site["auto_update"] else "no"
        if not scan:
            lines.append(f"| {site['name']} | - | - | - | - | - | {auto} | never scanned |")
            continue
        if scan["status"] != "ok":
            lines.append(f"| {site['name']} | - | - | - | - | - | {auto} | ERROR: {scan['error']} |")
            continue
        core = "yes" if scan["count_core"] else "-"
        lines.append(
            f"| {site['name']} | {scan['wp_version'] or '-'} | {scan['php_version'] or '-'} | "
            f"{core} | {scan['count_plugins']} | {scan['count_themes']} | {auto} | ok |"
        )

    # Per-site detail of what needs updating.
    detail = ["", "## Pending update detail", ""]
    any_detail = False
    for row in rows:
        site, scan = row["site"], row["scan"]
        if not scan or scan["status"] != "ok" or scan["count_total"] == 0:
            continue
        any_detail = True
        detail.append(f"### {site['name']}")
        if scan["core_update"]:
            cu = scan["core_update"]
            detail.append(f"- Core: {cu.get('current')} → {cu.get('available')}")
        for p in scan["plugins"]:
            if p.get("update"):
                detail.append(f"- Plugin: {p['name']} {p['current']} → {p.get('available')}")
        for t in scan["themes"]:
            if t.get("update"):
                detail.append(f"- Theme: {t['name']} {t['current']} → {t.get('available')}")
        detail.append("")
    if any_detail:
        lines += detail
    return "\n".join(lines)


def build_html() -> str:
    rows, totals = _gather()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def badge(n: int) -> str:
        cls = "ok" if n == 0 else "warn"
        return f'<span class="badge {cls}">{n}</span>'

    body = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        "<title>WordPress Update Report</title>",
        "<style>",
        "body{font-family:Segoe UI,Arial,sans-serif;margin:24px;color:#1c1e21;background:#f5f6f7}",
        "h1{font-size:20px}h2{font-size:16px;margin-top:28px}",
        "table{border-collapse:collapse;width:100%;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.1)}",
        "th,td{padding:8px 10px;border-bottom:1px solid #e4e6eb;text-align:left;font-size:13px}",
        "th{background:#1d2939;color:#fff}",
        ".badge{display:inline-block;min-width:20px;text-align:center;padding:2px 8px;border-radius:10px;font-weight:600}",
        ".badge.ok{background:#e3f6e8;color:#1a7f37}.badge.warn{background:#fde2e1;color:#b42318}",
        ".err{color:#b42318}.muted{color:#65676b}",
        ".summary{display:flex;gap:16px;margin:16px 0;flex-wrap:wrap}",
        ".card{background:#fff;border-radius:8px;padding:12px 18px;box-shadow:0 1px 3px rgba(0,0,0,.1)}",
        ".card b{display:block;font-size:22px}",
        "</style></head><body>",
        f"<h1>WordPress Update Report</h1><p class='muted'>{now}</p>",
        "<div class='summary'>",
        f"<div class='card'><b>{totals['sites']}</b>sites</div>",
        f"<div class='card'><b>{totals['total']}</b>pending updates</div>",
        f"<div class='card'><b>{totals['plugins']}</b>plugin updates</div>",
        f"<div class='card'><b>{totals['themes']}</b>theme updates</div>",
        f"<div class='card'><b>{totals['errors']}</b>errors</div>",
        "</div>",
        "<table><thead><tr><th>Site</th><th>WP</th><th>PHP</th><th>Core</th>"
        "<th>Plugins</th><th>Themes</th><th>Auto-update</th><th>Status</th></tr></thead><tbody>",
    ]
    for row in rows:
        site, scan = row["site"], row["scan"]
        auto = "✓" if site["auto_update"] else "—"
        name = escape(site["name"])
        if not scan:
            body.append(f"<tr><td>{name}</td><td colspan='6' class='muted'>never scanned</td><td>{auto}</td></tr>")
            continue
        if scan["status"] != "ok":
            body.append(
                f"<tr><td>{name}</td><td colspan='5' class='err'>ERROR: {escape(scan['error'] or '')}</td>"
                f"<td>{auto}</td><td class='err'>error</td></tr>"
            )
            continue
        core_badge = badge(scan["count_core"])
        body.append(
            f"<tr><td>{name}</td><td>{escape(scan['wp_version'] or '-')}</td>"
            f"<td>{escape(scan['php_version'] or '-')}</td><td>{core_badge}</td>"
            f"<td>{badge(scan['count_plugins'])}</td><td>{badge(scan['count_themes'])}</td>"
            f"<td>{auto}</td><td>ok</td></tr>"
        )
    body.append("</tbody></table>")

    # Detail
    body.append("<h2>Pending update detail</h2>")
    any_detail = False
    for row in rows:
        site, scan = row["site"], row["scan"]
        if not scan or scan["status"] != "ok" or scan["count_total"] == 0:
            continue
        any_detail = True
        body.append(f"<h3>{escape(site['name'])}</h3><ul>")
        if scan["core_update"]:
            cu = scan["core_update"]
            body.append(f"<li>Core: {escape(str(cu.get('current')))} → {escape(str(cu.get('available')))}</li>")
        for p in scan["plugins"]:
            if p.get("update"):
                body.append(f"<li>Plugin: {escape(p['name'])} {escape(str(p['current']))} → {escape(str(p.get('available')))}</li>")
        for t in scan["themes"]:
            if t.get("update"):
                body.append(f"<li>Theme: {escape(t['name'])} {escape(str(t['current']))} → {escape(str(t.get('available')))}</li>")
        body.append("</ul>")
    if not any_detail:
        body.append("<p class='muted'>No pending updates. 🎉</p>")

    body.append("</body></html>")
    return "".join(body)


def save_reports() -> Dict[str, str]:
    os.makedirs(config.reports_dir, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    html_path = os.path.join(config.reports_dir, f"report_{stamp}.html")
    md_path = os.path.join(config.reports_dir, f"report_{stamp}.md")
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(build_html())
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(build_markdown())
    return {"html": html_path, "md": md_path}


def has_pending_updates() -> bool:
    _, totals = _gather()
    return totals["total"] > 0


# --------------------------------------------------------------------------- #
# Weekly digest
# --------------------------------------------------------------------------- #
def _age_days(iso: str) -> Optional[int]:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0, int((datetime.now(timezone.utc) - dt).total_seconds() // 86400))


def _digest_data() -> Dict[str, Any]:
    """Gather the richer per-site data used by the weekly digest."""
    from . import health as health_mod  # local import avoids any import cycle
    from . import vuln as vuln_mod

    rows, totals = _gather()
    sites = []
    vuln_total = 0
    unhealthy = 0
    for row in rows:
        site, scan = row["site"], row["scan"]
        seen = db.get_update_seen_map(site["id"])
        ages = [d for d in (_age_days(v) for v in seen.values()) if d is not None]
        oldest = max(ages) if ages else None
        vulns = vuln_mod.get_findings(site["id"])
        vuln_total += int(vulns.get("count") or 0)
        h = health_mod.get_health(site["id"]) or {}
        if h.get("status") in ("down", "degraded"):
            unhealthy += 1
        sites.append({
            "name": site["name"],
            "pending": scan["count_total"] if scan and scan["status"] == "ok" else 0,
            "error": (scan["error"] if scan and scan["status"] != "ok" else None),
            "oldestPendingDays": oldest,
            "vulnCount": int(vulns.get("count") or 0),
            "health": h.get("status") or "unknown",
        })

    # Updates applied in the last 7 days.
    applied = 0
    for a in db.list_activity(limit=500):
        if not str(a.get("action", "")).startswith("update"):
            continue
        if a.get("status") not in ("success", "partial"):
            continue
        d = _age_days(a.get("created_at"))
        if d is not None and d <= 7:
            applied += 1

    return {
        "totals": totals,
        "sites": sites,
        "vulnTotal": vuln_total,
        "unhealthy": unhealthy,
        "appliedLast7": applied,
    }


def build_digest_markdown() -> str:
    d = _digest_data()
    t = d["totals"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# WordPress Weekly Digest — {now}",
        "",
        f"- Sites monitored: **{t['sites']}**",
        f"- Pending updates: **{t['total']}** (core {t['core']}, plugins {t['plugins']}, themes {t['themes']})",
        f"- Updates applied (last 7 days): **{d['appliedLast7']}**",
        f"- Known vulnerabilities: **{d['vulnTotal']}**",
        f"- Sites needing attention (errors/unhealthy): **{t['errors'] + d['unhealthy']}**",
        "",
        "| Site | Pending | Oldest (days) | Vulns | Health |",
        "|------|--------:|--------------:|------:|--------|",
    ]
    for s in d["sites"]:
        oldest = "—" if s["oldestPendingDays"] is None else str(s["oldestPendingDays"])
        pending = "ERROR" if s["error"] else str(s["pending"])
        lines.append(
            f"| {s['name']} | {pending} | {oldest} | {s['vulnCount']} | {s['health']} |"
        )
    return "\n".join(lines)


def build_digest_html() -> str:
    d = _digest_data()
    t = d["totals"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def badge(n: int, warn_over: int = 0) -> str:
        cls = "ok" if n <= warn_over else "warn"
        return f'<span class="badge {cls}">{n}</span>'

    body = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        "<title>WordPress Weekly Digest</title>",
        "<style>",
        "body{font-family:Segoe UI,Arial,sans-serif;margin:24px;color:#1c1e21;background:#f5f6f7}",
        "h1{font-size:20px}h2{font-size:16px;margin-top:28px}",
        "table{border-collapse:collapse;width:100%;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.1)}",
        "th,td{padding:8px 10px;border-bottom:1px solid #e4e6eb;text-align:left;font-size:13px}",
        "th{background:#1d2939;color:#fff}",
        ".badge{display:inline-block;min-width:20px;text-align:center;padding:2px 8px;border-radius:10px;font-weight:600}",
        ".badge.ok{background:#e3f6e8;color:#1a7f37}.badge.warn{background:#fde2e1;color:#b42318}",
        ".muted{color:#65676b}.summary{display:flex;gap:16px;margin:16px 0;flex-wrap:wrap}",
        ".card{background:#fff;border-radius:8px;padding:12px 18px;box-shadow:0 1px 3px rgba(0,0,0,.1)}",
        ".card b{display:block;font-size:22px}",
        "</style></head><body>",
        f"<h1>WordPress Weekly Digest</h1><p class='muted'>{now}</p>",
        "<div class='summary'>",
        f"<div class='card'><b>{t['sites']}</b>sites</div>",
        f"<div class='card'><b>{t['total']}</b>pending updates</div>",
        f"<div class='card'><b>{d['appliedLast7']}</b>applied (7d)</div>",
        f"<div class='card'><b>{d['vulnTotal']}</b>vulnerabilities</div>",
        f"<div class='card'><b>{t['errors'] + d['unhealthy']}</b>need attention</div>",
        "</div>",
        "<table><thead><tr><th>Site</th><th>Pending</th><th>Oldest (days)</th>"
        "<th>Vulns</th><th>Health</th></tr></thead><tbody>",
    ]
    for s in d["sites"]:
        name = escape(s["name"])
        if s["error"]:
            body.append(
                f"<tr><td>{name}</td><td colspan='4' class='badge warn'>ERROR: {escape(str(s['error']))}</td></tr>"
            )
            continue
        oldest = "—" if s["oldestPendingDays"] is None else str(s["oldestPendingDays"])
        health = escape(s["health"])
        body.append(
            f"<tr><td>{name}</td><td>{badge(s['pending'])}</td><td>{oldest}</td>"
            f"<td>{badge(s['vulnCount'])}</td><td>{health}</td></tr>"
        )
    body.append("</tbody></table></body></html>")
    return "".join(body)


def build_digest_text() -> str:
    """Plain-ish HTML summary suitable for a Telegram message."""
    from html import escape as esc
    d = _digest_data()
    t = d["totals"]
    lines = [
        "<b>WordPress Weekly Digest</b>",
        f"Sites: {t['sites']} · Pending: {t['total']} "
        f"(core {t['core']}, plugins {t['plugins']}, themes {t['themes']})",
        f"Applied (7d): {d['appliedLast7']} · Vulnerabilities: {d['vulnTotal']} · "
        f"Need attention: {t['errors'] + d['unhealthy']}",
    ]
    detail = []
    for s in d["sites"]:
        if s["error"]:
            detail.append(f"• <b>{esc(s['name'])}</b>: ERROR")
            continue
        bits = [f"{s['pending']} pending"]
        if s["oldestPendingDays"]:
            bits.append(f"oldest {s['oldestPendingDays']}d")
        if s["vulnCount"]:
            bits.append(f"⚠️ {s['vulnCount']} vuln")
        if s["health"] in ("down", "degraded"):
            bits.append(f"health {s['health']}")
        detail.append(f"• <b>{esc(s['name'])}</b>: " + ", ".join(bits))
    if detail:
        lines.append("")
        lines.extend(detail)
    return "\n".join(lines)
