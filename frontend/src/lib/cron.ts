// Helpers to translate between the friendly schedule form and a 5-field cron
// expression (minute hour day-of-month month day-of-week). The backend stores
// and validates the cron string; this module only builds/parses the common
// shapes the UI offers and falls back to "custom" for anything else.

export type ScanFrequency =
  | 'hourly'
  | 'daily'
  | 'multiple'
  | 'weekly'
  | 'monthly'
  | 'custom';

export interface ScheduleForm {
  frequency: ScanFrequency;
  everyHours: number; // hourly: run every N hours
  minute: number; // minute used by hourly / multiple
  time: string; // 'HH:MM' used by daily / weekly / monthly
  hours: number[]; // multiple-times-a-day: which hours (share `minute`)
  weekdays: number[]; // weekly: 0=Sun .. 6=Sat
  monthDay: number; // monthly: day of month 1-31
  custom: string; // custom cron expression
}

export const WEEKDAY_LABELS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

export const DEFAULT_SCHEDULE_FORM: ScheduleForm = {
  frequency: 'daily',
  everyHours: 6,
  minute: 0,
  time: '06:00',
  hours: [0, 6, 12, 18],
  weekdays: [1],
  monthDay: 1,
  custom: '0 6 * * *',
};

function pad(n: number): string {
  return n.toString().padStart(2, '0');
}

function parseTime(time: string): [number, number] {
  const [h, m] = time.split(':');
  const hour = Number.parseInt(h, 10);
  const minute = Number.parseInt(m, 10);
  return [Number.isNaN(hour) ? 0 : hour, Number.isNaN(minute) ? 0 : minute];
}

/** Build a cron expression from the friendly form. */
export function formToCron(form: ScheduleForm): string {
  switch (form.frequency) {
    case 'hourly': {
      const minute = clamp(form.minute, 0, 59);
      const every = clamp(form.everyHours, 1, 23);
      const hourField = every <= 1 ? '*' : `*/${every}`;
      return `${minute} ${hourField} * * *`;
    }
    case 'daily': {
      const [h, m] = parseTime(form.time);
      return `${m} ${h} * * *`;
    }
    case 'multiple': {
      const minute = clamp(form.minute, 0, 59);
      const hours = [...new Set(form.hours)].sort((a, b) => a - b);
      const hourField = hours.length ? hours.join(',') : '0';
      return `${minute} ${hourField} * * *`;
    }
    case 'weekly': {
      const [h, m] = parseTime(form.time);
      const days = [...new Set(form.weekdays)].sort((a, b) => a - b);
      const dowField = days.length ? days.join(',') : '1';
      return `${m} ${h} * * ${dowField}`;
    }
    case 'monthly': {
      const [h, m] = parseTime(form.time);
      const day = clamp(form.monthDay, 1, 31);
      return `${m} ${h} ${day} * *`;
    }
    case 'custom':
    default:
      return form.custom.trim();
  }
}

/** Best-effort parse of a cron expression back into the friendly form. */
export function cronToForm(cron: string): ScheduleForm {
  const form: ScheduleForm = { ...DEFAULT_SCHEDULE_FORM, custom: cron.trim() };
  const parts = cron.trim().split(/\s+/);
  if (parts.length !== 5) {
    return { ...form, frequency: 'custom' };
  }
  const [min, hr, dom, mon, dow] = parts;
  const numeric = (v: string) => /^\d+$/.test(v);

  // Hourly: every hour or every N hours, others unrestricted.
  if (dom === '*' && mon === '*' && dow === '*' && (hr === '*' || /^\*\/\d+$/.test(hr))) {
    return {
      ...form,
      frequency: 'hourly',
      everyHours: hr === '*' ? 1 : Number.parseInt(hr.slice(2), 10),
      minute: numeric(min) ? Number.parseInt(min, 10) : 0,
    };
  }
  // Several times a day: comma-separated hours, single numeric minute.
  if (dom === '*' && mon === '*' && dow === '*' && hr.includes(',') && numeric(min)) {
    const hours = hr.split(',').filter(numeric).map((h) => Number.parseInt(h, 10));
    return { ...form, frequency: 'multiple', minute: Number.parseInt(min, 10), hours };
  }
  // Plain daily.
  if (dom === '*' && mon === '*' && dow === '*' && numeric(min) && numeric(hr)) {
    return {
      ...form,
      frequency: 'daily',
      time: `${pad(Number.parseInt(hr, 10))}:${pad(Number.parseInt(min, 10))}`,
    };
  }
  // Weekly.
  if (dom === '*' && mon === '*' && dow !== '*' && numeric(min) && numeric(hr)) {
    const days = dow
      .split(',')
      .filter(numeric)
      .map((d) => Number.parseInt(d, 10) % 7);
    return {
      ...form,
      frequency: 'weekly',
      time: `${pad(Number.parseInt(hr, 10))}:${pad(Number.parseInt(min, 10))}`,
      weekdays: days.length ? days : [1],
    };
  }
  // Monthly.
  if (dom !== '*' && mon === '*' && dow === '*' && numeric(min) && numeric(hr) && numeric(dom)) {
    return {
      ...form,
      frequency: 'monthly',
      time: `${pad(Number.parseInt(hr, 10))}:${pad(Number.parseInt(min, 10))}`,
      monthDay: Number.parseInt(dom, 10),
    };
  }
  return { ...form, frequency: 'custom' };
}

function clamp(n: number, lo: number, hi: number): number {
  if (Number.isNaN(n)) return lo;
  return Math.max(lo, Math.min(hi, n));
}
