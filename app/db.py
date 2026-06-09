"""SQLite persistence layer (stdlib sqlite3, no ORM).

Tables
------
sites    : registered WordPress sites + per-site preferences
scans    : one row per poll of a site (latest + history)
settings : key/value store for GUI-editable global settings (SMTP, schedule)
"""
import json
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .config import config

_lock = threading.Lock()


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_conn() -> sqlite3.Connection:
    os.makedirs(config.DATA_DIR, exist_ok=True)
    _migrate_legacy_db()
    conn = sqlite3.connect(config.db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def _migrate_legacy_db() -> None:
    """One-time rename of the pre-rename wpmonitor.db to wpupdater.db so the
    existing registered sites and history survive the WP_Updater rename."""
    new = config.db_path
    legacy = config.legacy_db_path
    if os.path.exists(new) or not os.path.exists(legacy):
        return
    for suffix in ("", "-wal", "-shm"):
        src = legacy + suffix
        dst = new + suffix
        if os.path.exists(src) and not os.path.exists(dst):
            try:
                os.rename(src, dst)
            except OSError:
                pass


def init_db() -> None:
    with _lock, get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sites (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            TEXT NOT NULL,
                url             TEXT NOT NULL UNIQUE,
                api_key         TEXT NOT NULL,
                enabled         INTEGER NOT NULL DEFAULT 1,
                auto_update     INTEGER NOT NULL DEFAULT 0,
                notify_admin    INTEGER NOT NULL DEFAULT 0,
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS scans (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                site_id         INTEGER NOT NULL,
                scanned_at      TEXT NOT NULL,
                status          TEXT NOT NULL,          -- ok | error
                error           TEXT,
                wp_version      TEXT,
                php_version     TEXT,
                connector_version TEXT,
                core_update     TEXT,                   -- JSON or NULL
                plugins         TEXT,                   -- JSON array
                themes          TEXT,                   -- JSON array
                count_core      INTEGER NOT NULL DEFAULT 0,
                count_plugins   INTEGER NOT NULL DEFAULT 0,
                count_themes    INTEGER NOT NULL DEFAULT 0,
                count_total     INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_scans_site_time
                ON scans(site_id, scanned_at DESC);

            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS activity (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                site_id     INTEGER,
                site_name   TEXT NOT NULL,
                action      TEXT NOT NULL,          -- scan | update-core | update-plugins | update-themes | update-all
                status      TEXT NOT NULL,          -- success | failed | partial | idle
                duration_ms INTEGER NOT NULL DEFAULT 0,
                error       TEXT,
                details     TEXT,                   -- JSON array or NULL
                created_at  TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_activity_time
                ON activity(created_at DESC);
            """
        )
        # ---- lightweight migrations -------------------------------------
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(sites)").fetchall()}
        if "grp" not in cols:
            conn.execute("ALTER TABLE sites ADD COLUMN grp TEXT NOT NULL DEFAULT 'Ungrouped'")
        if "last_updated_at" not in cols:
            conn.execute("ALTER TABLE sites ADD COLUMN last_updated_at TEXT")
        if "notify_telegram" not in cols:
            conn.execute("ALTER TABLE sites ADD COLUMN notify_telegram INTEGER NOT NULL DEFAULT 0")
        scan_cols = {r["name"] for r in conn.execute("PRAGMA table_info(scans)").fetchall()}
        if "connector_version" not in scan_cols:
            conn.execute("ALTER TABLE scans ADD COLUMN connector_version TEXT")
        activity_cols = {r["name"] for r in conn.execute("PRAGMA table_info(activity)").fetchall()}
        if "resolved" not in activity_cols:
            conn.execute("ALTER TABLE activity ADD COLUMN resolved INTEGER NOT NULL DEFAULT 0")


# --------------------------------------------------------------------------- #
# Settings helpers
# --------------------------------------------------------------------------- #
def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with _lock, get_conn() as conn:
        conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


def get_settings_dict() -> Dict[str, str]:
    with get_conn() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}


def seed_settings_if_empty() -> None:
    """Seed GUI settings from environment defaults on first boot only."""
    if get_setting("_seeded") == "1":
        return
    defaults = {
        "scan_enabled": "1" if config.SCAN_ENABLED else "0",
        "scan_hour": str(config.SCAN_HOUR),
        "scan_minute": str(config.SCAN_MINUTE),
        "smtp_host": config.SMTP_HOST,
        "smtp_port": str(config.SMTP_PORT),
        "smtp_user": config.SMTP_USER,
        "smtp_password": config.SMTP_PASSWORD,
        "smtp_from": config.SMTP_FROM,
        "smtp_tls": "1" if config.SMTP_TLS else "0",
        "report_recipients": config.REPORT_RECIPIENTS,
        "email_only_when_updates": "1" if config.EMAIL_ONLY_WHEN_UPDATES else "0",
        "email_enabled": "1" if config.SMTP_HOST else "0",
        "telegram_bot_token": config.TELEGRAM_BOT_TOKEN,
        "telegram_chat_id": config.TELEGRAM_CHAT_ID,
        "telegram_only_when_updates": "1" if config.TELEGRAM_ONLY_WHEN_UPDATES else "0",
        "telegram_enabled": "1" if (config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID) else "0",
    }
    for k, v in defaults.items():
        if get_setting(k) is None:
            set_setting(k, v)
    set_setting("_seeded", "1")


# --------------------------------------------------------------------------- #
# Site CRUD
# --------------------------------------------------------------------------- #
def _normalize_url(url: str) -> str:
    return url.strip().rstrip("/")


def add_site(name: str, url: str, api_key: str, auto_update: bool = False,
             notify_admin: bool = False, enabled: bool = True,
             grp: str = "Ungrouped", notify_telegram: bool = False) -> int:
    now = _utcnow()
    with _lock, get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO sites(name, url, api_key, enabled, auto_update, notify_admin, notify_telegram, grp, created_at, updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            (name.strip(), _normalize_url(url), api_key.strip(),
             1 if enabled else 0, 1 if auto_update else 0,
             1 if notify_admin else 0, 1 if notify_telegram else 0,
             (grp or "Ungrouped").strip(), now, now),
        )
        return int(cur.lastrowid)


def update_site(site_id: int, **fields: Any) -> None:
    if not fields:
        return
    allowed = {"name", "url", "api_key", "enabled", "auto_update", "notify_admin", "notify_telegram", "grp"}
    cols, vals = [], []
    for k, v in fields.items():
        if k not in allowed:
            continue
        if k == "url":
            v = _normalize_url(v)
        if k in ("enabled", "auto_update", "notify_admin", "notify_telegram"):
            v = 1 if v else 0
        cols.append(f"{k}=?")
        vals.append(v)
    if not cols:
        return
    cols.append("updated_at=?")
    vals.append(_utcnow())
    vals.append(site_id)
    with _lock, get_conn() as conn:
        conn.execute(f"UPDATE sites SET {', '.join(cols)} WHERE id=?", vals)


def delete_site(site_id: int) -> None:
    with _lock, get_conn() as conn:
        conn.execute("DELETE FROM sites WHERE id=?", (site_id,))


def get_site(site_id: int) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM sites WHERE id=?", (site_id,)).fetchone()
        return dict(row) if row else None


def list_sites(enabled_only: bool = False) -> List[Dict[str, Any]]:
    q = "SELECT * FROM sites"
    if enabled_only:
        q += " WHERE enabled=1"
    q += " ORDER BY name COLLATE NOCASE"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(q).fetchall()]


# --------------------------------------------------------------------------- #
# Scans
# --------------------------------------------------------------------------- #
def record_scan(site_id: int, status: str, payload: Optional[Dict[str, Any]] = None,
                error: Optional[str] = None) -> int:
    payload = payload or {}
    counts = payload.get("counts", {}) or {}
    with _lock, get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO scans(site_id, scanned_at, status, error, wp_version, php_version, "
            "connector_version, core_update, plugins, themes, count_core, count_plugins, count_themes, count_total) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                site_id, _utcnow(), status, error,
                payload.get("wp_version"), payload.get("php_version"),
                payload.get("connector_version"),
                json.dumps(payload.get("core_update")) if payload.get("core_update") else None,
                json.dumps(payload.get("plugins", [])),
                json.dumps(payload.get("themes", [])),
                int(counts.get("core", 0)),
                int(counts.get("plugins", 0)),
                int(counts.get("themes", 0)),
                int(counts.get("total", 0)),
            ),
        )
        return int(cur.lastrowid)


def latest_scan(site_id: int) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM scans WHERE site_id=? ORDER BY scanned_at DESC LIMIT 1",
            (site_id,),
        ).fetchone()
        return _decode_scan(row) if row else None


def scan_history(site_id: int, limit: int = 30) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM scans WHERE site_id=? ORDER BY scanned_at DESC LIMIT ?",
            (site_id, limit),
        ).fetchall()
        return [_decode_scan(r) for r in rows]


def prune_scans(site_id: int, keep: int = 200) -> None:
    with _lock, get_conn() as conn:
        conn.execute(
            "DELETE FROM scans WHERE site_id=? AND id NOT IN "
            "(SELECT id FROM scans WHERE site_id=? ORDER BY scanned_at DESC LIMIT ?)",
            (site_id, site_id, keep),
        )


def _decode_scan(row: sqlite3.Row) -> Dict[str, Any]:
    d = dict(row)
    d["core_update"] = json.loads(d["core_update"]) if d.get("core_update") else None
    d["plugins"] = json.loads(d["plugins"]) if d.get("plugins") else []
    d["themes"] = json.loads(d["themes"]) if d.get("themes") else []
    return d


# --------------------------------------------------------------------------- #
# Activity log
# --------------------------------------------------------------------------- #
def record_activity(site_id: Optional[int], site_name: str, action: str,
                    status: str, duration_ms: int = 0,
                    error: Optional[str] = None,
                    details: Optional[List[Dict[str, Any]]] = None) -> int:
    with _lock, get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO activity(site_id, site_name, action, status, duration_ms, error, details, created_at) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (site_id, site_name, action, status, int(duration_ms), error,
             json.dumps(details) if details else None, _utcnow()),
        )
        return int(cur.lastrowid)


def list_activity(limit: int = 100) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM activity ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["details"] = json.loads(d["details"]) if d.get("details") else None
            out.append(d)
        return out


def resolve_activity(entry_id: int) -> None:
    """Mark a single activity entry resolved so it stops counting on the
    dashboard tile. The entry itself is left untouched in the log."""
    with _lock, get_conn() as conn:
        conn.execute("UPDATE activity SET resolved=1 WHERE id=?", (entry_id,))


def resolve_site_failures(site_id: int) -> None:
    """Clear the dashboard error warning for a site by marking its prior
    failed/partial entries resolved (used after a successful update)."""
    with _lock, get_conn() as conn:
        conn.execute(
            "UPDATE activity SET resolved=1 "
            "WHERE site_id=? AND status IN ('failed','partial') AND resolved=0",
            (site_id,),
        )


def prune_activity(keep: int = 500) -> None:
    with _lock, get_conn() as conn:
        conn.execute(
            "DELETE FROM activity WHERE id NOT IN "
            "(SELECT id FROM activity ORDER BY created_at DESC LIMIT ?)",
            (keep,),
        )


def touch_last_updated(site_id: int) -> None:
    with _lock, get_conn() as conn:
        conn.execute("UPDATE sites SET last_updated_at=? WHERE id=?", (_utcnow(), site_id))
