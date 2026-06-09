import type { ActivityLogEntry, DashboardSummary, Site } from '../types';

export function buildSummary(sites: Site[], activity: ActivityLogEntry[]): DashboardSummary {
  const sitesWithUpdates = sites.filter((s) => s.totalUpdates > 0).length;
  const coreUpdates = sites.filter((s) => s.coreUpdateAvailable).length;
  const pluginUpdates = sites.reduce((n, s) => n + s.pluginUpdatesCount, 0);
  const themeUpdates = sites.reduce((n, s) => n + s.themeUpdatesCount, 0);
  const failedActions = activity.filter(
    (a) => (a.status === 'failed' || a.status === 'partial') && !a.resolved,
  ).length;
  const lastScanAt = sites
    .map((s) => s.lastScanAt)
    .filter((v): v is string => Boolean(v))
    .sort()
    .reverse()[0] ?? null;
  return {
    totalSites: sites.length,
    sitesWithUpdates,
    coreUpdates,
    pluginUpdates,
    themeUpdates,
    failedActions,
    lastScanAt,
  };
}

/** Filter sites by a free-text query across name, url and group. */
export function filterSitesByQuery(sites: Site[], query: string): Site[] {
  const q = query.trim().toLowerCase();
  if (!q) return sites;
  return sites.filter(
    (s) =>
      s.name.toLowerCase().includes(q) ||
      s.url.toLowerCase().includes(q) ||
      s.group.toLowerCase().includes(q),
  );
}
