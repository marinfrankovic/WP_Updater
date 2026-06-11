import { useEffect, useState } from 'react';
import { CalendarClock, Mail, MessageCircle, Moon, RefreshCw, Save, Send, Sun } from 'lucide-react';
import { useApp } from '../state/AppContext';
import { apiClient, type EmailSettings, type ScanSchedule, type TelegramSettings } from '../api/client';
import {
  cronToForm,
  formToCron,
  WEEKDAY_LABELS,
  type ScanFrequency,
  type ScheduleForm,
} from '../lib/cron';

function pad(n: number): string {
  return n.toString().padStart(2, '0');
}

function formatRun(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}

const FREQUENCY_OPTIONS: { value: ScanFrequency; label: string }[] = [
  { value: 'hourly', label: 'Hourly' },
  { value: 'daily', label: 'Daily' },
  { value: 'multiple', label: 'Several times a day' },
  { value: 'weekly', label: 'Weekly' },
  { value: 'monthly', label: 'Monthly' },
  { value: 'custom', label: 'Custom cron' },
];

export function SettingsPage() {
  const { state, setTheme, pushToast } = useApp();

  // -------------------------------------------------------------- schedule
  const [schedule, setSchedule] = useState<ScanSchedule | null>(null);
  const [enabled, setEnabled] = useState(true);
  const [form, setForm] = useState<ScheduleForm>(() => cronToForm('0 6 * * *'));
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // ----------------------------------------------------------------- email
  const [email, setEmail] = useState<EmailSettings | null>(null);
  const [emailForm, setEmailForm] = useState({
    enabled: false,
    host: '',
    port: 587,
    user: '',
    from: '',
    tls: true,
    recipients: '',
    onlyWhenUpdates: true,
    password: '',
  });
  const [emailSaving, setEmailSaving] = useState(false);
  const [testRecipient, setTestRecipient] = useState('');
  const [emailTesting, setEmailTesting] = useState(false);

  // -------------------------------------------------------------- telegram
  const [telegram, setTelegram] = useState<TelegramSettings | null>(null);
  const [tgForm, setTgForm] = useState({
    enabled: false,
    chatId: '',
    onlyWhenUpdates: true,
    token: '',
  });
  const [tgSaving, setTgSaving] = useState(false);
  const [tgTesting, setTgTesting] = useState(false);

  useEffect(() => {
    let active = true;
    Promise.all([apiClient.getSchedule(), apiClient.getEmail(), apiClient.getTelegram()])
      .then(([s, e, t]) => {
        if (!active) return;
        setSchedule(s);
        setEnabled(s.enabled);
        setForm(cronToForm(s.cron || `${s.minute} ${s.hour} * * *`));

        setEmail(e);
        setEmailForm({
          enabled: e.enabled,
          host: e.host,
          port: e.port,
          user: e.user,
          from: e.from,
          tls: e.tls,
          recipients: e.recipients,
          onlyWhenUpdates: e.onlyWhenUpdates,
          password: '',
        });

        setTelegram(t);
        setTgForm({
          enabled: t.enabled,
          chatId: t.chatId,
          onlyWhenUpdates: t.onlyWhenUpdates,
          token: '',
        });
      })
      .catch((err) => {
        pushToast({ title: 'Could not load settings', message: String(err), variant: 'error' });
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [pushToast]);

  async function saveSchedule() {
    const cron = formToCron(form).trim();
    if (!cron || cron.split(/\s+/).length !== 5) {
      pushToast({
        title: 'Invalid schedule',
        message: 'Enter a valid 5-field cron expression (minute hour day month weekday).',
        variant: 'error',
      });
      return;
    }
    if (form.frequency === 'multiple' && form.hours.length === 0) {
      pushToast({ title: 'Pick at least one time', message: 'Select the hours to scan at.', variant: 'error' });
      return;
    }
    if (form.frequency === 'weekly' && form.weekdays.length === 0) {
      pushToast({ title: 'Pick at least one day', message: 'Select the weekday(s) to scan on.', variant: 'error' });
      return;
    }
    setSaving(true);
    try {
      const res = await apiClient.setSchedule({ enabled, cron });
      setSchedule(res.schedule);
      setEnabled(res.schedule.enabled);
      setForm(cronToForm(res.schedule.cron));
      pushToast({ title: 'Scan schedule saved', message: res.schedule.description, variant: 'success' });
    } catch (err) {
      pushToast({ title: 'Could not save schedule', message: String(err), variant: 'error' });
    } finally {
      setSaving(false);
    }
  }

  function patchForm(patch: Partial<ScheduleForm>) {
    setForm((prev) => ({ ...prev, ...patch }));
  }

  function toggleInArray(arr: number[], value: number): number[] {
    return arr.includes(value) ? arr.filter((v) => v !== value) : [...arr, value];
  }

  const previewCron = formToCron(form).trim();

  async function saveEmail() {
    setEmailSaving(true);
    try {
      const patch: Partial<Omit<EmailSettings, 'passwordSet'>> & { password?: string } = {
        enabled: emailForm.enabled,
        host: emailForm.host.trim(),
        port: emailForm.port,
        user: emailForm.user.trim(),
        from: emailForm.from.trim(),
        tls: emailForm.tls,
        recipients: emailForm.recipients,
        onlyWhenUpdates: emailForm.onlyWhenUpdates,
      };
      if (emailForm.password.trim()) patch.password = emailForm.password;
      const res = await apiClient.setEmail(patch);
      setEmail(res.email);
      setEmailForm((f) => ({ ...f, password: '' }));
      pushToast({ title: 'Email settings saved', variant: 'success' });
    } catch (err) {
      pushToast({ title: 'Could not save email settings', message: String(err), variant: 'error' });
    } finally {
      setEmailSaving(false);
    }
  }

  async function sendTestEmail() {
    const recipient = testRecipient.trim();
    if (!recipient) {
      pushToast({ title: 'Enter a recipient', message: 'Provide an address to test', variant: 'error' });
      return;
    }
    setEmailTesting(true);
    try {
      const res = await apiClient.testEmail(recipient);
      pushToast({ title: 'Test email sent', message: res.message, variant: 'success' });
    } catch (err) {
      pushToast({ title: 'Test email failed', message: String(err), variant: 'error' });
    } finally {
      setEmailTesting(false);
    }
  }

  async function saveTelegram() {
    setTgSaving(true);
    try {
      const patch: Partial<Omit<TelegramSettings, 'tokenSet'>> & { token?: string } = {
        enabled: tgForm.enabled,
        chatId: tgForm.chatId.trim(),
        onlyWhenUpdates: tgForm.onlyWhenUpdates,
      };
      if (tgForm.token.trim()) patch.token = tgForm.token.trim();
      const res = await apiClient.setTelegram(patch);
      setTelegram(res.notifications);
      setTgForm((f) => ({ ...f, token: '' }));
      pushToast({ title: 'Telegram settings saved', variant: 'success' });
    } catch (err) {
      pushToast({ title: 'Could not save Telegram settings', message: String(err), variant: 'error' });
    } finally {
      setTgSaving(false);
    }
  }

  async function sendTestTelegram() {
    setTgTesting(true);
    try {
      const override: { chatId?: string; token?: string } = {};
      if (tgForm.chatId.trim()) override.chatId = tgForm.chatId.trim();
      if (tgForm.token.trim()) override.token = tgForm.token.trim();
      const res = await apiClient.testTelegram(override);
      pushToast({ title: 'Test message sent', message: res.message, variant: 'success' });
    } catch (err) {
      pushToast({ title: 'Test message failed', message: String(err), variant: 'error' });
    } finally {
      setTgTesting(false);
    }
  }

  return (
    <div className="page">
      <div className="page__head">
        <div>
          <h1>Settings</h1>
          <p className="page__sub">Appearance, scan schedule and notifications</p>
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
          WP Updater automatically scans every site on a schedule you choose and sends a report. Updates are never
          installed automatically — they are only ever applied when you click Update.
        </p>

        {loading ? (
          <p className="muted">
            <RefreshCw size={16} className="spin" /> Loading settings…
          </p>
        ) : (
          <div className="schedule-form">
            <label className="schedule-toggle">
              <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
              <span>Run automatic scans</span>
            </label>

            <div className="schedule-field">
              <label htmlFor="scan-frequency">Frequency</label>
              <select
                id="scan-frequency"
                value={form.frequency}
                disabled={!enabled}
                onChange={(e) => patchForm({ frequency: e.target.value as ScanFrequency })}
              >
                {FREQUENCY_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            {form.frequency === 'hourly' && (
              <div className="schedule-row">
                <div className="schedule-field">
                  <label htmlFor="every-hours">Run every (hours)</label>
                  <select
                    id="every-hours"
                    value={form.everyHours}
                    disabled={!enabled}
                    onChange={(e) => patchForm({ everyHours: Number.parseInt(e.target.value, 10) })}
                  >
                    {[1, 2, 3, 4, 6, 8, 12].map((n) => (
                      <option key={n} value={n}>
                        {n === 1 ? 'Every hour' : `Every ${n} hours`}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="schedule-field">
                  <label htmlFor="hourly-minute">At minute</label>
                  <input
                    id="hourly-minute"
                    type="number"
                    min={0}
                    max={59}
                    value={form.minute}
                    disabled={!enabled}
                    onChange={(e) => patchForm({ minute: Number.parseInt(e.target.value, 10) || 0 })}
                  />
                </div>
              </div>
            )}

            {form.frequency === 'daily' && (
              <div className="schedule-field">
                <label htmlFor="scan-time">Scan time (server time)</label>
                <input
                  id="scan-time"
                  type="time"
                  value={form.time}
                  disabled={!enabled}
                  onChange={(e) => patchForm({ time: e.target.value })}
                />
              </div>
            )}

            {form.frequency === 'multiple' && (
              <>
                <div className="schedule-field">
                  <label>Run at these hours</label>
                  <div className="schedule-chips">
                    {Array.from({ length: 24 }, (_, h) => h).map((h) => (
                      <button
                        type="button"
                        key={h}
                        className={`schedule-chip${form.hours.includes(h) ? ' is-active' : ''}`}
                        disabled={!enabled}
                        onClick={() => patchForm({ hours: toggleInArray(form.hours, h) })}
                      >
                        {pad(h)}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="schedule-field">
                  <label htmlFor="multi-minute">At minute</label>
                  <input
                    id="multi-minute"
                    type="number"
                    min={0}
                    max={59}
                    value={form.minute}
                    disabled={!enabled}
                    onChange={(e) => patchForm({ minute: Number.parseInt(e.target.value, 10) || 0 })}
                  />
                </div>
              </>
            )}

            {form.frequency === 'weekly' && (
              <>
                <div className="schedule-field">
                  <label>On these days</label>
                  <div className="schedule-chips">
                    {WEEKDAY_LABELS.map((label, idx) => (
                      <button
                        type="button"
                        key={label}
                        className={`schedule-chip${form.weekdays.includes(idx) ? ' is-active' : ''}`}
                        disabled={!enabled}
                        onClick={() => patchForm({ weekdays: toggleInArray(form.weekdays, idx) })}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="schedule-field">
                  <label htmlFor="weekly-time">Scan time (server time)</label>
                  <input
                    id="weekly-time"
                    type="time"
                    value={form.time}
                    disabled={!enabled}
                    onChange={(e) => patchForm({ time: e.target.value })}
                  />
                </div>
              </>
            )}

            {form.frequency === 'monthly' && (
              <div className="schedule-row">
                <div className="schedule-field">
                  <label htmlFor="month-day">Day of month</label>
                  <input
                    id="month-day"
                    type="number"
                    min={1}
                    max={31}
                    value={form.monthDay}
                    disabled={!enabled}
                    onChange={(e) => patchForm({ monthDay: Number.parseInt(e.target.value, 10) || 1 })}
                  />
                </div>
                <div className="schedule-field">
                  <label htmlFor="monthly-time">Scan time (server time)</label>
                  <input
                    id="monthly-time"
                    type="time"
                    value={form.time}
                    disabled={!enabled}
                    onChange={(e) => patchForm({ time: e.target.value })}
                  />
                </div>
              </div>
            )}

            {form.frequency === 'custom' && (
              <div className="schedule-field">
                <label htmlFor="custom-cron">Cron expression</label>
                <input
                  id="custom-cron"
                  type="text"
                  spellCheck={false}
                  placeholder="minute hour day-of-month month day-of-week"
                  value={form.custom}
                  disabled={!enabled}
                  onChange={(e) => patchForm({ custom: e.target.value })}
                />
                <span className="muted" style={{ fontSize: '12px' }}>
                  Standard 5-field cron, e.g. <code>0 */6 * * *</code> = every 6 hours.
                </span>
              </div>
            )}

            <p className="muted schedule-next">
              Schedule: <code>{previewCron || '—'}</code>
              {schedule?.description ? <> · {schedule.description}</> : null}
            </p>

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
        <h2 className="settings-card__title">
          <Mail size={18} /> Email reports (SMTP)
        </h2>
        <p className="muted">
          Send the update report by email after the daily scan. Configure your SMTP server below.
        </p>

        {loading ? (
          <p className="muted">
            <RefreshCw size={16} className="spin" /> Loading…
          </p>
        ) : (
          <div className="schedule-form">
            <label className="schedule-toggle">
              <input
                type="checkbox"
                checked={emailForm.enabled}
                onChange={(e) => setEmailForm({ ...emailForm, enabled: e.target.checked })}
              />
              <span>Enable email reports</span>
            </label>

            <div className="settings-grid">
              <div className="schedule-field">
                <label htmlFor="smtp-host">SMTP host</label>
                <input
                  id="smtp-host"
                  type="text"
                  value={emailForm.host}
                  placeholder="smtp.example.com"
                  onChange={(e) => setEmailForm({ ...emailForm, host: e.target.value })}
                />
              </div>
              <div className="schedule-field">
                <label htmlFor="smtp-port">Port</label>
                <input
                  id="smtp-port"
                  type="number"
                  min={1}
                  max={65535}
                  value={emailForm.port}
                  onChange={(e) => setEmailForm({ ...emailForm, port: Number.parseInt(e.target.value, 10) || 0 })}
                />
              </div>
              <div className="schedule-field">
                <label htmlFor="smtp-user">Username</label>
                <input
                  id="smtp-user"
                  type="text"
                  autoComplete="off"
                  value={emailForm.user}
                  onChange={(e) => setEmailForm({ ...emailForm, user: e.target.value })}
                />
              </div>
              <div className="schedule-field">
                <label htmlFor="smtp-password">
                  Password {email?.passwordSet ? <span className="muted">(set — leave blank to keep)</span> : null}
                </label>
                <input
                  id="smtp-password"
                  type="password"
                  autoComplete="new-password"
                  value={emailForm.password}
                  placeholder={email?.passwordSet ? '••••••••' : ''}
                  onChange={(e) => setEmailForm({ ...emailForm, password: e.target.value })}
                />
              </div>
              <div className="schedule-field">
                <label htmlFor="smtp-from">From address</label>
                <input
                  id="smtp-from"
                  type="email"
                  value={emailForm.from}
                  placeholder="wp-updater@example.com"
                  onChange={(e) => setEmailForm({ ...emailForm, from: e.target.value })}
                />
              </div>
              <div className="schedule-field">
                <label htmlFor="smtp-recipients">Recipients (comma-separated)</label>
                <input
                  id="smtp-recipients"
                  type="text"
                  value={emailForm.recipients}
                  placeholder="admin@example.com, ops@example.com"
                  onChange={(e) => setEmailForm({ ...emailForm, recipients: e.target.value })}
                />
              </div>
            </div>

            <label className="schedule-toggle">
              <input
                type="checkbox"
                checked={emailForm.tls}
                onChange={(e) => setEmailForm({ ...emailForm, tls: e.target.checked })}
              />
              <span>Use STARTTLS (port 465 uses implicit SSL automatically)</span>
            </label>
            <label className="schedule-toggle">
              <input
                type="checkbox"
                checked={emailForm.onlyWhenUpdates}
                onChange={(e) => setEmailForm({ ...emailForm, onlyWhenUpdates: e.target.checked })}
              />
              <span>Only send when there are pending updates</span>
            </label>

            <button className="btn btn--primary schedule-save" onClick={saveEmail} disabled={emailSaving}>
              {emailSaving ? <RefreshCw size={16} className="spin" /> : <Save size={16} />}
              {emailSaving ? 'Saving…' : 'Save email settings'}
            </button>

            <div className="settings-test">
              <input
                type="email"
                value={testRecipient}
                placeholder="you@example.com"
                onChange={(e) => setTestRecipient(e.target.value)}
              />
              <button className="btn btn--ghost" onClick={sendTestEmail} disabled={emailTesting}>
                {emailTesting ? <RefreshCw size={16} className="spin" /> : <Send size={16} />}
                {emailTesting ? 'Sending…' : 'Send test email'}
              </button>
            </div>
          </div>
        )}
      </section>

      <section className="card settings-card">
        <h2 className="settings-card__title">
          <MessageCircle size={18} /> Telegram notifications
        </h2>
        <p className="muted">
          Receive a short update summary in a Telegram chat. Create a bot with @BotFather to get a token, then send it a
          message and use your numeric chat id below.
        </p>

        {loading ? (
          <p className="muted">
            <RefreshCw size={16} className="spin" /> Loading…
          </p>
        ) : (
          <div className="schedule-form">
            <label className="schedule-toggle">
              <input
                type="checkbox"
                checked={tgForm.enabled}
                onChange={(e) => setTgForm({ ...tgForm, enabled: e.target.checked })}
              />
              <span>Enable Telegram notifications</span>
            </label>

            <div className="settings-grid">
              <div className="schedule-field">
                <label htmlFor="tg-token">
                  Bot token {telegram?.tokenSet ? <span className="muted">(set — leave blank to keep)</span> : null}
                </label>
                <input
                  id="tg-token"
                  type="password"
                  autoComplete="new-password"
                  value={tgForm.token}
                  placeholder={telegram?.tokenSet ? '••••••••' : '123456:ABC-DEF…'}
                  onChange={(e) => setTgForm({ ...tgForm, token: e.target.value })}
                />
              </div>
              <div className="schedule-field">
                <label htmlFor="tg-chat">Chat id</label>
                <input
                  id="tg-chat"
                  type="text"
                  value={tgForm.chatId}
                  placeholder="123456789"
                  onChange={(e) => setTgForm({ ...tgForm, chatId: e.target.value })}
                />
              </div>
            </div>

            <label className="schedule-toggle">
              <input
                type="checkbox"
                checked={tgForm.onlyWhenUpdates}
                onChange={(e) => setTgForm({ ...tgForm, onlyWhenUpdates: e.target.checked })}
              />
              <span>Only send when there are pending updates</span>
            </label>

            <button className="btn btn--primary schedule-save" onClick={saveTelegram} disabled={tgSaving}>
              {tgSaving ? <RefreshCw size={16} className="spin" /> : <Save size={16} />}
              {tgSaving ? 'Saving…' : 'Save Telegram settings'}
            </button>

            <div className="settings-test">
              <button className="btn btn--ghost" onClick={sendTestTelegram} disabled={tgTesting}>
                {tgTesting ? <RefreshCw size={16} className="spin" /> : <Send size={16} />}
                {tgTesting ? 'Sending…' : 'Send test message'}
              </button>
            </div>
          </div>
        )}
      </section>

      <section className="card settings-card">
        <h2>Scope</h2>
        <p className="muted">
          This dashboard is intentionally focused on updating WordPress core, plugins and themes. Security scanning, uptime
          and backups are out of scope for this version.
        </p>
      </section>
    </div>
  );
}
