"""Background scheduler: a single daemon thread that runs the daily scan and
emails a report. No external dependencies (stdlib threading + time)."""
import threading
import time
from datetime import datetime, timedelta
from typing import Optional

from . import db, emailer, reports, scanner

_thread: Optional[threading.Thread] = None
_stop = threading.Event()
# Set whenever the schedule settings change (or on shutdown) so the loop wakes
# up early and recomputes the next run instead of waiting out its current sleep.
_wake = threading.Event()
_state = {"last_run": None, "next_run": None, "running": False}
_run_lock = threading.Lock()


def request_reschedule() -> None:
    """Nudge the scheduler thread to re-read settings and recompute next run."""
    _wake.set()


def run_scan_cycle(send_email: bool = True) -> dict:
    """Scan all enabled sites, write reports, optionally email. Thread-safe."""
    with _run_lock:
        _state["running"] = True
        try:
            results = scanner.scan_all(enabled_only=True)
            reports.save_reports()
            email_msg = None
            if send_email:
                ok, email_msg = emailer.send_report(force=False)
            _state["last_run"] = datetime.now().isoformat(timespec="seconds")
            return {"results": results, "email": email_msg}
        finally:
            _state["running"] = False


def _seconds_until_next(hour: int, minute: int) -> float:
    now = datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    _state["next_run"] = target.isoformat(timespec="seconds")
    return (target - now).total_seconds()


def _loop() -> None:
    while not _stop.is_set():
        _wake.clear()
        settings = db.get_settings_dict()
        if settings.get("scan_enabled", "1") != "1":
            # Sleep until woken by a settings change (or shutdown).
            _state["next_run"] = None
            _wake.wait(3600)
            continue
        hour = int(settings.get("scan_hour", "6") or "6")
        minute = int(settings.get("scan_minute", "0") or "0")
        wait_s = _seconds_until_next(hour, minute)
        # Wake at least once an hour to re-read the schedule, or immediately if
        # the schedule was changed via the settings API.
        woke = _wake.wait(min(wait_s, 3600))
        if _stop.is_set():
            break
        if woke:
            # Settings changed -> recompute next run from the top of the loop.
            continue
        if wait_s <= 3600:
            try:
                run_scan_cycle(send_email=True)
            except Exception:  # noqa: BLE001 - never let the scheduler thread die
                pass
            _stop.wait(60)  # avoid double-trigger within the same minute


def start() -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _wake.clear()
    _thread = threading.Thread(target=_loop, name="wpupdater-scheduler", daemon=True)
    _thread.start()


def stop() -> None:
    _stop.set()
    _wake.set()


def status() -> dict:
    return dict(_state)
