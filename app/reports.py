"""HTML / Markdown report generation from the latest scan per site."""
import os
from datetime import datetime, timezone
from html import escape
from typing import Any, Dict, List, Tuple

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
