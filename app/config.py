"""Runtime configuration, loaded from environment variables.

All values have safe defaults so the app can boot with an empty .env. The web
GUI persists operational settings (SMTP, schedule) in the database; environment
variables only seed the initial values on first run.
"""
import os


def _env(name: str, default=None):
    """Read WPUPDATER_<name>, falling back to the legacy WPMONITOR_<name>."""
    val = os.environ.get(f"WPUPDATER_{name}")
    if val is None:
        val = os.environ.get(f"WPMONITOR_{name}")
    return val if val is not None else default


def _bool(name: str, default: bool) -> bool:
    val = _env(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _plain_bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


class Config:
    # Where the SQLite database and generated reports live (mounted volume).
    DATA_DIR = _env("DATA_DIR", "/data")

    # Web server
    HOST = _env("HOST", "0.0.0.0")
    PORT = int(_env("PORT", "8090"))
    SECRET_KEY = _env("SECRET_KEY", "change-me-in-production")
    TZ = os.environ.get("TZ", "UTC")

    # Optional HTTP basic auth for the dashboard itself.
    DASHBOARD_USER = _env("USER", "")
    DASHBOARD_PASSWORD = _env("PASSWORD", "")

    # Connector HTTP behaviour
    REQUEST_TIMEOUT = int(_env("REQUEST_TIMEOUT", "30"))
    VERIFY_TLS = _bool("VERIFY_TLS", True)

    # Scheduler seed values (editable later in the GUI -> settings table)
    SCAN_ENABLED = _bool("SCAN_ENABLED", True)
    SCAN_HOUR = int(_env("SCAN_HOUR", "6"))
    SCAN_MINUTE = int(_env("SCAN_MINUTE", "0"))

    # SMTP seed values
    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USER = os.environ.get("SMTP_USER", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_FROM = os.environ.get("SMTP_FROM", "")
    SMTP_TLS = _plain_bool("SMTP_TLS", True)
    # Comma-separated list of dashboard admin recipients.
    REPORT_RECIPIENTS = os.environ.get("REPORT_RECIPIENTS", "")
    # When true, email reports are sent only if at least one site has updates.
    EMAIL_ONLY_WHEN_UPDATES = _bool("EMAIL_ONLY_WHEN_UPDATES", True)

    @property
    def db_path(self) -> str:
        return os.path.join(self.DATA_DIR, "wpupdater.db")

    @property
    def legacy_db_path(self) -> str:
        return os.path.join(self.DATA_DIR, "wpmonitor.db")

    @property
    def reports_dir(self) -> str:
        return os.path.join(self.DATA_DIR, "reports")


config = Config()
