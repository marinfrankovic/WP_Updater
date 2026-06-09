// Domain models for WP Updater (updates-only scope).
// These interfaces are the contract the future REST API will fulfil, so the UI
// can switch from mock data to live data without structural changes.

/** Lifecycle/progress state shared by sites and update items. */
export type ProgressStatus =
  | 'idle'
  | 'scanning'
  | 'updating'
  | 'success'
  | 'failed'
  | 'partial';

/** The three kinds of WordPress updates we manage. */
export type UpdateType = 'core' | 'plugin' | 'theme';

/** Per-item update lifecycle (a single plugin/theme/core row). */
export type UpdateItemStatus =
  | 'available'
  | 'updating'
  | 'success'
  | 'failed'
  | 'up-to-date';

/** Actions recorded in the activity log. */
export type ActivityAction =
  | 'scan'
  | 'update-core'
  | 'update-plugins'
  | 'update-themes'
  | 'update-all';

export interface Site {
  id: string;
  name: string;
  url: string;
  wordpressVersion: string;
  connectorVersion: string | null;
  coreUpdateAvailable: boolean;
  pluginUpdatesCount: number;
  themeUpdatesCount: number;
  totalUpdates: number;
  status: ProgressStatus;
  lastScanAt: string | null; // ISO timestamp
  lastUpdatedAt: string | null; // ISO timestamp
  autoUpdate: boolean;
  notifyAdmin: boolean;
  notifyTelegram: boolean;
  group: string;
  selected: boolean;
  /** Progress 0–100 while scanning/updating (UI-only, optional). */
  progress?: number;
}

export interface UpdateItem {
  id: string;
  siteId: string;
  type: UpdateType;
  slug: string;
  name: string;
  currentVersion: string;
  availableVersion: string;
  status: UpdateItemStatus;
  selected: boolean;
}

export interface ActivityLogEntry {
  id: string;
  timestamp: string; // ISO
  siteId: string;
  siteName: string;
  action: ActivityAction;
  status: ProgressStatus;
  /** Duration in milliseconds. */
  durationMs: number;
  /** Populated when status is 'failed' or 'partial'. */
  error?: string;
  /** Optional per-item breakdown for expandable error details. */
  details?: { name: string; result: 'success' | 'failed'; message?: string }[];
  /** When true, this failure no longer counts on the dashboard tile. */
  resolved: boolean;
}

/** Top-of-dashboard summary widgets. */
export interface DashboardSummary {
  totalSites: number;
  sitesWithUpdates: number;
  coreUpdates: number;
  pluginUpdates: number;
  themeUpdates: number;
  failedActions: number;
  lastScanAt: string | null;
}

export type ThemeMode = 'light' | 'dark';

export type RouteKey = 'dashboard' | 'sites' | 'updates' | 'activity' | 'settings' | 'help';

export interface Toast {
  id: string;
  title: string;
  message?: string;
  variant: 'success' | 'error' | 'warning' | 'info';
}
