import { useEffect, useState } from 'react';
import { CalendarClock, Moon, RefreshCw, Save, Sun } from 'lucide-react';
import { useApp } from '../state/AppContext';
import { apiClient, type ScanSchedule } from '../api/client';

function pad(n: number): string {
  return n.toString().padStart(2, '0');
}

function formatRun(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}

export function SettingsPage() {
  const { state, setTheme, pushToast } = useApp();

  const [schedule, setSchedule] = useState<ScanSchedule | null>(null);
  const [enabled, setEnabled] = useState(true);
  const [time, setTime] = useState('06:00');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let active = true;
    apiClient
      .getSchedule()
      .then((s) => {
        if (!active) return;
        setSchedule(s);
        setEnabled(s.enabled);
        setTime(`${pad(s.hour)}:${pad(s.minute)}`);
      })
      .catch((err) => {
        pushToast({ title: 'Could not load schedule', message: String(err), variant: 'error' });
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [pushToast]);

  async function saveSchedule() {
    const [hourStr, minuteStr] = time.split(':');
    const hour = Number.parseInt(hourStr, 10);
    const minute = Number.parseInt(minuteStr, 10);
    if (Number.isNaN(hour) || Number.isNaN(minute)) {
      pushToast({ title: 'Invalid time', message: 'Pick a valid scan time', variant: 'error' });
      return;
    }
    setSaving(true);
    try {
      const res = await apiClient.setSchedule({ enabled, hour, minute });
      setSchedule(res.schedule);
      setEnabled(res.schedule.enabled);
      setTime(`${pad(res.schedule.hour)}:${pad(res.schedule.minute)}`);
      pushToast({ title: 'Scan schedule saved', variant: 'success' });
    } catch (err) {
      pushToast({ title: 'Could not save schedule', message: String(err), variant: 'error' });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page">
      <div className="page__head">
        <div>
          <h1>Settings</h1>
          <p className="page__sub">Appearance and scan preferences</p>
        </div>
      </div>

      <section className="card settings-card">
        <h2>Appearance</h2>
        <p className="muted">Choose how WP Updater looks.</p>
        <div className="theme-options">
          <button className={`theme-option${state.theme === 'light' ? ' is-active' : ''}`} onClick={() => setTheme('light')}>
            <Sun size={18} /> Light
          </button>
          <button className={`theme-option${state.theme === 'dark' ? ' is-active' : ''}`} onClick={() => setTheme('dark')}>
            <Moon size={18} /> Dark
          </button>
        </div>
      </section>

      <section className="card settings-card">
        <h2 className="settings-card__title">
          <CalendarClock size={18} /> Scan schedule
        </h2>
        <p className="muted">
          WP Updater automatically scans every site once a day for available updates and emails a report. Updates are never
          installed automatically — they are only ever applied when you click Update.
        </p>

        {loading ? (
          <p className="muted">
            <RefreshCw size={16} className="spin" /> Loading schedule…
          </p>
        ) : (
          <div className="schedule-form">
            <label className="schedule-toggle">
              <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
              <span>Run the daily automatic scan</span>
            </label>

            <div className="schedule-field">
              <label htmlFor="scan-time">Scan time (server time)</label>
              <input
                id="scan-time"
                type="time"
                value={time}
                disabled={!enabled}
                onChange={(e) => setTime(e.target.value)}
              />
            </div>

            <p className="muted schedule-next">
              Next run: <strong>{enabled ? formatRun(schedule?.nextRun ?? null) : 'Disabled'}</strong>
              {schedule?.lastRun ? <> · Last run: {formatRun(schedule.lastRun)}</> : null}
            </p>

            <button className="btn btn--primary schedule-save" onClick={saveSchedule} disabled={saving}>
              {saving ? <RefreshCw size={16} className="spin" /> : <Save size={16} />}
              {saving ? 'Saving…' : 'Save schedule'}
            </button>
          </div>
        )}
      </section>

      <section className="card settings-card">
        <h2>Scope</h2>
        <p className="muted">
          This dashboard is intentionally focused on updating WordPress core, plugins and themes. Security scanning, uptime,
          backups and reporting are out of scope for this version.
        </p>
      </section>
    </div>
  );
}
