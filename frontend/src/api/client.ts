import type { ActivityLogEntry, Site, UpdateItem, UpdateType } from '../types';

// The SPA is served from the same Flask origin in production, so relative URLs
// hit the backend directly. In dev, Vite proxies /api to the Flask server.
const BASE = '/api';

export interface ServerState {
  sites: Site[];
  updates: UpdateItem[];
  activity: ActivityLogEntry[];
}

export interface ScanSchedule {
  enabled: boolean;
  hour: number;
  minute: number;
  cron: string;
  description: string;
  nextRun: string | null;
  lastRun: string | null;
}

export interface EmailSettings {
  enabled: boolean;
  host: string;
  port: number;
  user: string;
  from: string;
  tls: boolean;
  recipients: string;
  onlyWhenUpdates: boolean;
  passwordSet: boolean;
}

export interface TelegramSettings {
  enabled: boolean;
  chatId: string;
  onlyWhenUpdates: boolean;
  tokenSet: boolean;
}

export interface SecuritySettings {
  enabled: boolean;
  cacheTtlHours: number;
  tokenSet: boolean;
}

export interface DigestSettings {
  enabled: boolean;
  cron: string;
  description: string;
  channels: string;
}

export interface UpdateCommands {
  publishedImage: string[];
  sourceBuild: string[];
}

export interface AppInfo {
  currentVersion: string;
  commands: UpdateCommands;
}

export interface AppUpdateInfo extends AppInfo {
  latestVersion: string | null;
  updateAvailable: boolean;
  releaseName: string | null;
  releaseNotes: string | null;
  releaseUrl: string | null;
  error: string | null;
}

export interface VulnFinding {
  type: string;
  slug: string;
  name: string;
  installedVersion: string | null;
  title: string | null;
  fixedIn: string | null;
  cves: string[];
}

export interface SiteVulns {
  siteId: string;
  siteName: string;
  checkedAt: string | null;
  count: number;
  findings: VulnFinding[];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body?.error) detail = body.error;
    } catch {
      /* ignore non-JSON bodies */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export const apiClient = {
  getState: () => request<ServerState>('/state'),

  getAppInfo: () => request<AppInfo>('/app-info'),

  checkAppUpdate: () => request<AppUpdateInfo>('/app-update'),

  addSite: (input: { name: string; url: string; apiKey: string; group: string }) =>
    request<{ ok: boolean; state: ServerState }>('/sites', {
      method: 'POST',
      body: JSON.stringify(input),
    }),

  removeSite: (id: string) =>
    request<{ ok: boolean; state: ServerState }>(`/sites/${id}`, { method: 'DELETE' }),

  editSite: (
    id: string,
    patch: {
      name?: string;
      url?: string;
      apiKey?: string;
      group?: string;
      notifyAdmin?: boolean;
      notifyTelegram?: boolean;
    },
  ) =>
    request<{ ok: boolean; state: ServerState }>(`/sites/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(patch),
    }),

  scanSite: (id: string) =>
    request<{ ok: boolean; state: ServerState }>(`/sites/${id}/scan`, { method: 'POST' }),

  scanAll: () => request<{ ok: boolean; state: ServerState }>('/scan-all', { method: 'POST' }),

  updateSite: (id: string, scope: UpdateType | 'all') =>
    request<{ ok: boolean; state: ServerState }>(`/sites/${id}/update`, {
      method: 'POST',
      body: JSON.stringify({ scope }),
    }),

  updateItem: (id: string, type: UpdateType, slug: string) =>
    request<{ ok: boolean; state: ServerState }>(`/sites/${id}/update-item`, {
      method: 'POST',
      body: JSON.stringify({ type, slug }),
    }),

  setAutoUpdate: (id: string, enabled: boolean) =>
    request<{ ok: boolean; state: ServerState }>(`/sites/${id}/auto-update`, {
      method: 'POST',
      body: JSON.stringify({ enabled }),
    }),

  bulkUpdate: (siteIds: string[], scope: UpdateType | 'all') =>
    request<{ ok: boolean; state: ServerState }>('/bulk-update', {
      method: 'POST',
      body: JSON.stringify({ siteIds, scope }),
    }),

  resolveActivity: (id: string) =>
    request<{ ok: boolean; state: ServerState }>(`/activity/${id}/resolve`, { method: 'POST' }),

  getSchedule: () => request<ScanSchedule>('/schedule'),

  setSchedule: (patch: Partial<Pick<ScanSchedule, 'enabled' | 'hour' | 'minute' | 'cron'>>) =>
    request<{ ok: boolean; schedule: ScanSchedule }>('/schedule', {
      method: 'POST',
      body: JSON.stringify(patch),
    }),

  getEmail: () => request<EmailSettings>('/email'),

  setEmail: (
    patch: Partial<Omit<EmailSettings, 'passwordSet'>> & { password?: string },
  ) =>
    request<{ ok: boolean; email: EmailSettings }>('/email', {
      method: 'POST',
      body: JSON.stringify(patch),
    }),

  testEmail: (recipient: string) =>
    request<{ ok: boolean; message: string }>('/email/test', {
      method: 'POST',
      body: JSON.stringify({ recipient }),
    }),

  getTelegram: () => request<TelegramSettings>('/notifications'),

  setTelegram: (
    patch: Partial<Omit<TelegramSettings, 'tokenSet'>> & { token?: string },
  ) =>
    request<{ ok: boolean; notifications: TelegramSettings }>('/notifications', {
      method: 'POST',
      body: JSON.stringify(patch),
    }),

  testTelegram: (override?: { chatId?: string; token?: string }) =>
    request<{ ok: boolean; message: string }>('/notifications/test', {
      method: 'POST',
      body: JSON.stringify(override ?? {}),
    }),

  getSecurity: () => request<SecuritySettings>('/security'),

  setSecurity: (
    patch: Partial<Omit<SecuritySettings, 'tokenSet'>> & { token?: string },
  ) =>
    request<{ ok: boolean; security: SecuritySettings }>('/security', {
      method: 'POST',
      body: JSON.stringify(patch),
    }),

  scanVulns: () => request<{ ok: boolean; state: ServerState }>('/vulns/scan', { method: 'POST' }),

  getVulns: () => request<{ sites: SiteVulns[] }>('/vulns'),

  healthCheck: (id: string) =>
    request<{ ok: boolean; state: ServerState }>(`/sites/${id}/health`, { method: 'POST' }),

  getDigest: () => request<DigestSettings>('/digest'),

  setDigest: (patch: Partial<Pick<DigestSettings, 'enabled' | 'cron' | 'channels'>>) =>
    request<{ ok: boolean; digest: DigestSettings }>('/digest', {
      method: 'POST',
      body: JSON.stringify(patch),
    }),

  testDigest: () =>
    request<{ ok: boolean; message: string }>('/digest/test', { method: 'POST' }),
};
