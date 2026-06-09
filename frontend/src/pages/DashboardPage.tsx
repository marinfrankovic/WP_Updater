import { Activity, AlertTriangle, Globe, Package, Palette, RefreshCw, Server, Zap } from 'lucide-react';
import { useApp } from '../state/AppContext';
import { buildSummary } from '../state/selectors';
import { SummaryCard } from '../components/SummaryCard';
import { SitesTable } from '../components/SitesTable';
import { ActivityLogTable } from '../components/ActivityLogTable';
import { EmptyState } from '../components/EmptyState';
import { relativeTime } from '../utils/format';

export function DashboardPage() {
  const { state, setRoute, setUpdatesTab, scanAll } = useApp();
  const summary = buildSummary(state.sites, state.activity);

  const attention = [...state.sites]
    .filter((s) => s.totalUpdates > 0)
    .sort((a, b) => b.totalUpdates - a.totalUpdates)
    .slice(0, 6);

  const goToUpdates = (tab: 'all' | 'core' | 'plugin' | 'theme') => {
    setUpdatesTab(tab);
    setRoute('updates');
  };

  return (
    <div className="page">
      <div className="page__head">
        <div>
          <h1>Dashboard</h1>
          <p className="page__sub">Update overview across {summary.totalSites} WordPress sites · last scan {relativeTime(summary.lastScanAt)}</p>
        </div>
        <button className="btn btn--ghost" onClick={scanAll}>
          <RefreshCw size={15} /> Scan all
        </button>
      </div>

      <div className="summary-grid">
        <SummaryCard label="Total sites" value={summary.totalSites} icon={<Server size={18} />} tone="neutral" onClick={() => setRoute('sites')} />
        <SummaryCard label="Sites with updates" value={summary.sitesWithUpdates} icon={<AlertTriangle size={18} />} tone={summary.sitesWithUpdates ? 'warning' : 'success'} onClick={() => goToUpdates('all')} />
        <SummaryCard label="Core updates" value={summary.coreUpdates} icon={<Globe size={18} />} tone={summary.coreUpdates ? 'warning' : 'success'} onClick={() => goToUpdates('core')} />
        <SummaryCard label="Plugin updates" value={summary.pluginUpdates} icon={<Package size={18} />} tone={summary.pluginUpdates ? 'warning' : 'success'} onClick={() => goToUpdates('plugin')} />
        <SummaryCard label="Theme updates" value={summary.themeUpdates} icon={<Palette size={18} />} tone={summary.themeUpdates ? 'warning' : 'success'} onClick={() => goToUpdates('theme')} />
        <SummaryCard label="Failed / partial" value={summary.failedActions} icon={<Zap size={18} />} tone={summary.failedActions ? 'danger' : 'success'} onClick={() => setRoute('activity')} />
      </div>

      <section className="section">
        <div className="section__head">
          <h2>Needs attention</h2>
          <button className="link-btn" onClick={() => setRoute('sites')}>View all sites</button>
        </div>
        {attention.length === 0 ? (
          <EmptyState icon={<Zap size={26} />} title="Everything is up to date" description="No sites currently have pending updates." />
        ) : (
          <SitesTable sites={attention} />
        )}
      </section>

      <section className="section">
        <div className="section__head">
          <h2>Recent activity</h2>
          <button className="link-btn" onClick={() => setRoute('activity')}>View log</button>
        </div>
        {state.activity.length === 0 ? (
          <EmptyState icon={<Activity size={26} />} title="No activity yet" description="Scans and updates will appear here." />
        ) : (
          <ActivityLogTable entries={state.activity.slice(0, 5)} />
        )}
      </section>
    </div>
  );
}
