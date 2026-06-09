import {
  Activity,
  HelpCircle,
  LayoutDashboard,
  RefreshCw,
  Server,
  Settings,
  ShieldCheck,
} from 'lucide-react';
import { useApp } from '../state/AppContext';
import type { RouteKey } from '../types';

const NAV: { key: RouteKey; label: string; icon: typeof LayoutDashboard }[] = [
  { key: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { key: 'sites', label: 'Sites', icon: Server },
  { key: 'updates', label: 'Updates', icon: RefreshCw },
  { key: 'activity', label: 'Activity Log', icon: Activity },
  { key: 'settings', label: 'Settings', icon: Settings },
  { key: 'help', label: 'Help', icon: HelpCircle },
];

export function Sidebar() {
  const { state, setRoute } = useApp();
  const pendingUpdates = state.sites.reduce((n, s) => n + s.totalUpdates, 0);

  return (
    <aside className="sidebar">
      <div className="sidebar__brand">
        <span className="sidebar__logo">
          <ShieldCheck size={18} />
        </span>
        <div className="sidebar__brand-text">
          <strong>WP Updater</strong>
        </div>
      </div>

      <nav className="sidebar__nav">
        {NAV.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            className={`sidebar__link${state.route === key ? ' is-active' : ''}`}
            onClick={() => setRoute(key)}
          >
            <Icon size={17} />
            <span>{label}</span>
            {key === 'updates' && pendingUpdates > 0 && (
              <span className="sidebar__badge">{pendingUpdates}</span>
            )}
          </button>
        ))}
      </nav>

      <div className="sidebar__footer">
        <div className="sidebar__footer-row">
          <span className="dot dot--success" />
          {state.sites.length} sites monitored
        </div>
      </div>
    </aside>
  );
}
