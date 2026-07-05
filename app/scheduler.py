"""Background scheduler: a single daemon thread that runs scheduled scans and
sends reports. No external dependencies (stdlib threading + time).

The schedule is driven by a standard 5-field cron expression
(``minute hour day-of-month month day-of-week``) stored in the ``scan_cron``
setting. This single engine covers every supported cadence — hourly, daily,
weekly, monthly, several times a day and fully custom cron — so the UI only has
to build the right expression. Installs that predate ``scan_cron`` fall back to
the legacy ``scan_hour``/``scan_minute`` daily time, so upgrades are seamless.
"""
import threading
import time
from datetime import datetime, timedelta
from typing import Optional, Set, Tuple

from . import db, emailer, reports, scanner, telegram

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
                try:
                    telegram.send_report(force=False)
                except Exception:  # noqa: BLE001 - never let a notifier kill the cycle
                    pass
            _state["last_run"] = datetime.now().isoformat(timespec="seconds")
            return {"results": results, "email": email_msg}
        finally:
            _state["running"] = False


def send_digest() -> None:
    """Send the weekly digest over the configured channels (best-effort)."""
    settings = db.get_settings_dict()
    if settings.get("digest_enabled", "0") != "1":
        return
    channels = {c.strip() for c in (settings.get("digest_channels", "email,telegram") or "").split(",") if c.strip()}
    if "email" in channels:
        try:
            emailer.send_digest(force=True)
        except Exception:  # noqa: BLE001 - never let a notifier kill the digest
            pass
    if "telegram" in channels:
        try:
            telegram.send_digest(force=True)
        except Exception:  # noqa: BLE001
            pass


_DOW_NAMES = {
    "sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6,
}
_MON_NAMES = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _parse_cron_field(field: str, lo: int, hi: int, names: Optional[dict] = None) -> Set[int]:
    """Parse one cron field into the set of integers it matches.

    Supports ``*``, lists (``a,b``), ranges (``a-b``), steps (``*/n``,
    ``a-b/n``) and three-letter month/weekday names. Raises ValueError on
    anything malformed so the caller can reject the whole expression.
    """
    field = field.strip()
    if field == "":
        raise ValueError("empty field")
    values: Set[int] = set()
    for part in field.split(","):
        part = part.strip().lower()
        step = 1
        if "/" in part:
            rng, _, step_s = part.partition("/")
            step = int(step_s)
            if step <= 0:
                raise ValueError("step must be positive")
        else:
            rng = part
        if rng in ("*", ""):
            start, end = lo, hi
        elif "-" in rng and not rng.startswith("-"):
            a_s, _, b_s = rng.partition("-")
            start = _field_int(a_s, names)
            end = _field_int(b_s, names)
        else:
            start = end = _field_int(rng, names)
        if start > end:
            raise ValueError(f"range start {start} > end {end}")
        v = start
        while v <= end:
            if not (lo <= v <= hi):
                raise ValueError(f"value {v} out of range {lo}-{hi}")
            values.add(v)
            v += step
    return values


def _field_int(token: str, names: Optional[dict]) -> int:
    token = token.strip().lower()
    if names and token in names:
        return names[token]
    return int(token)


def _parse_cron(expr: str) -> Tuple[Set[int], Set[int], Set[int], Set[int], Set[int]]:
    """Split a 5-field cron expression into matched-value sets.

    Returns (minutes, hours, days-of-month, months, days-of-week). Day-of-week
    is normalised to 0-6 (Sunday=0); a literal 7 is folded onto 0.
    """
    parts = expr.split()
    if len(parts) != 5:
        raise ValueError("cron expression must have exactly 5 fields")
    minutes = _parse_cron_field(parts[0], 0, 59)
    hours = _parse_cron_field(parts[1], 0, 23)
    dom = _parse_cron_field(parts[2], 1, 31)
    months = _parse_cron_field(parts[3], 1, 12, _MON_NAMES)
    dow = _parse_cron_field(parts[4], 0, 7, _DOW_NAMES)
    if 7 in dow:
        dow.discard(7)
        dow.add(0)
    return minutes, hours, dom, months, dow


def validate_cron(expr: str) -> Tuple[bool, Optional[str]]:
    """Return (ok, error) for a candidate cron expression."""
    try:
        _parse_cron(expr.strip())
        return True, None
    except Exception as exc:  # noqa: BLE001 - surface a friendly message
        return False, str(exc)


def _cron_matches(dt: datetime, fields: Tuple[Set[int], ...]) -> bool:
    minutes, hours, dom, months, dow = fields
    if dt.minute not in minutes or dt.hour not in hours or dt.month not in months:
        return False
    # cron day-of-week: Sunday=0 .. Saturday=6.
    cur_dow = dt.isoweekday() % 7
    dom_restricted = len(dom) < 31
    dow_restricted = len(dow) < 7
    dom_ok = dt.day in dom
    dow_ok = cur_dow in dow
    if dom_restricted and dow_restricted:
        # Standard cron rule: when BOTH are restricted, match either.
        return dom_ok or dow_ok
    if dom_restricted:
        return dom_ok
    if dow_restricted:
        return dow_ok
    return True


def next_cron_after(expr: str, now: datetime) -> Optional[datetime]:
    """Return the next datetime (minute resolution) strictly after ``now`` that
    matches ``expr``, searching up to ~366 days ahead. None if unparseable."""
    try:
        fields = _parse_cron(expr.strip())
    except Exception:  # noqa: BLE001
        return None
    candidate = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
    horizon = candidate + timedelta(days=366)
    while candidate <= horizon:
        if _cron_matches(candidate, fields):
            return candidate
        candidate += timedelta(minutes=1)
    return None


def _effective_cron(settings: dict) -> str:
    """The cron expression in effect: stored ``scan_cron`` if set, else a daily
    expression derived from the legacy ``scan_hour``/``scan_minute`` settings."""
    expr = (settings.get("scan_cron") or "").strip()
    if expr:
        return expr
    try:
        hour = int(settings.get("scan_hour", "6") or 6)
    except (TypeError, ValueError):
        hour = 6
    try:
        minute = int(settings.get("scan_minute", "0") or 0)
    except (TypeError, ValueError):
        minute = 0
    hour = max(0, min(23, hour))
    minute = max(0, min(59, minute))
    return f"{minute} {hour} * * *"


def describe_cron(expr: str) -> str:
    """Best-effort human description of a cron expression for the UI."""
    expr = expr.strip()
    ok, _ = validate_cron(expr)
    if not ok:
        return "Invalid schedule"
    parts = expr.split()
    minute, hour, dom, month, dow = parts

    def _hhmm(h: str, m: str) -> str:
        try:
            return f"{int(h):02d}:{int(m):02d}"
        except ValueError:
            return f"{h}:{m}"

    # Every minute / every N minutes.
    if hour == "*" and dom == "*" and month == "*" and dow == "*":
        if minute == "*":
            return "Every minute"
        if minute.startswith("*/"):
            return f"Every {minute[2:]} minutes"
        if "," in minute:
            return f"Hourly at minutes {minute}"
        return f"Hourly at minute {minute}"
    # Every N hours.
    if hour.startswith("*/") and dom == "*" and month == "*" and dow == "*":
        return f"Every {hour[2:]} hours" + (f" at minute {minute}" if minute != "0" else "")
    # Multiple specific hours each day.
    if "," in hour and dom == "*" and month == "*" and dow == "*":
        times = ", ".join(_hhmm(h, minute) for h in hour.split(","))
        return f"Daily at {times}"
    # Weekly (specific day-of-week).
    if dow != "*" and dom == "*":
        day_labels = {0: "Sun", 1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat"}
        try:
            days = ", ".join(day_labels[int(d) % 7] for d in dow.replace("7", "0").split(","))
        except ValueError:
            days = dow
        return f"Weekly on {days} at {_hhmm(hour, minute)}"
    # Monthly (specific day-of-month).
    if dom != "*" and dow == "*":
        return f"Monthly on day {dom} at {_hhmm(hour, minute)}"
    # Plain daily.
    if dom == "*" and month == "*" and dow == "*":
        return f"Daily at {_hhmm(hour, minute)}"
    return f"Custom schedule ({expr})"


def _seconds_until_next(expr: str) -> Optional[float]:
    """Update ``_state['next_run']`` from ``expr`` and return seconds to wait."""
    now = datetime.now()
    nxt = next_cron_after(expr, now)
    if nxt is None:
        _state["next_run"] = None
        return None
    _state["next_run"] = nxt.isoformat(timespec="seconds")
    return max(0.0, (nxt - now).total_seconds())


def _loop() -> None:
    last_fired_minute: Optional[datetime] = None
    last_digest_minute: Optional[datetime] = None
    while not _stop.is_set():
        _wake.clear()
        settings = db.get_settings_dict()
        scan_on = settings.get("scan_enabled", "1") == "1"
        digest_on = settings.get("digest_enabled", "0") == "1"
        digest_expr = (settings.get("digest_cron") or "0 8 * * 1").strip()

        waits = [3600.0]
        scan_expr: Optional[str] = None
        if scan_on:
            scan_expr = _effective_cron(settings)
            ws = _seconds_until_next(scan_expr)  # also updates _state["next_run"]
            if ws is not None:
                waits.append(ws)
            else:
                scan_expr = None
        else:
            _state["next_run"] = None
        if digest_on:
            wd = next_cron_after(digest_expr, datetime.now())
            if wd is not None:
                waits.append(max(0.0, (wd - datetime.now()).total_seconds()))

        if scan_expr is None and not digest_on:
            # Nothing scheduled; wait for a settings change (or shutdown).
            _wake.wait(3600)
            continue

        woke = _wake.wait(min(waits))
        if _stop.is_set():
            break
        if woke:
            # Settings changed -> recompute everything from the top.
            continue

        this_minute = datetime.now().replace(second=0, microsecond=0)
        if scan_expr:
            try:
                if _cron_matches(this_minute, _parse_cron(scan_expr)) and this_minute != last_fired_minute:
                    last_fired_minute = this_minute
                    try:
                        run_scan_cycle(send_email=True)
                    except Exception:  # noqa: BLE001 - never let the scheduler thread die
                        pass
            except Exception:  # noqa: BLE001
                pass
        if digest_on:
            try:
                if _cron_matches(this_minute, _parse_cron(digest_expr)) and this_minute != last_digest_minute:
                    last_digest_minute = this_minute
                    try:
                        send_digest()
                    except Exception:  # noqa: BLE001
                        pass
            except Exception:  # noqa: BLE001
                pass
        _stop.wait(2)  # avoid re-evaluating the same minute repeatedly


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
