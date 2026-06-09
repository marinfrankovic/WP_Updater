import { ExternalLink, Package, Palette, Pencil, RefreshCw, Trash2, Zap } from 'lucide-react';
import { useApp } from '../state/AppContext';
import type { Site } from '../types';
import { relativeTime } from '../utils/format';
import { StatusBadge } from './StatusBadge';

interface SitesTableProps {
  sites: Site[];
}

export function SitesTable({ sites }: SitesTableProps) {
  const { toggleSite, setSitesSelected, openDrawer, scanSite, updateSite, removeSite, requestConfirm } = useApp();

  const allSelected = sites.length > 0 && sites.every((s) => s.selected);
  const someSelected = sites.some((s) => s.selected);

  const onUpdateAll = (site: Site) => {
    if (site.totalUpdates === 0) return;
    requestConfirm({
      title: `Update ${site.name}`,
      message: `Apply all ${site.totalUpdates} available update(s) (core, plugins, themes) on ${site.name}?`,
      confirmLabel: 'Update all',
      onConfirm: () => updateSite(site.id, 'all'),
    });
  };

  const onRemove = (site: Site) => {
    requestConfirm({
      title: `Remove ${site.name}`,
      message: `Remove ${site.name} from WP Updater? This deletes its stored scan history here but does not change the WordPress site itself.`,
      confirmLabel: 'Remove site',
      onConfirm: () => removeSite(site.id),
    });
  };

  return (
    <div className="card">
      <table className="data-table data-table--sites">
        <thead>
          <tr>
            <th className="col-check">
              <input
                type="checkbox"
                checked={allSelected}
                ref={(el) => {
                  if (el) el.indeterminate = someSelected && !allSelected;
                }}
                onChange={(e) => setSitesSelected(sites.map((s) => s.id), e.target.checked)}
                aria-label="Select all sites"
              />
            </th>
            <th>Site</th>
            <th>WP Core</th>
            <th>Connector</th>
            <th className="col-num">Plugins</th>
            <th className="col-num">Themes</th>
            <th className="col-num">Total</th>
            <th>Last scan</th>
            <th>Status</th>
            <th className="col-actions">Actions</th>
          </tr>
        </thead>
        <tbody>
          {sites.map((site) => {
            const busy = site.status === 'scanning' || site.status === 'updating';
            return (
              <tr key={site.id} className={site.selected ? 'is-selected' : ''}>
                <td className="col-check">
                  <input
                    type="checkbox"
                    checked={site.selected}
                    onChange={() => toggleSite(site.id)}
                    aria-label={`Select ${site.name}`}
                  />
                </td>
                <td>
                  <button className="link-cell" onClick={() => openDrawer(site.id)}>
                    <span className="link-cell__name">{site.name}</span>
                    <span className="link-cell__url">
                      {site.url.replace(/^https?:\/\//, '')}
                      <ExternalLink size={11} />
                    </span>
                  </button>
                </td>
                <td>
                  {site.coreUpdateAvailable ? (
                    <span className="pill pill--warning">Update</span>
                  ) : (
                    <span className="muted">{site.wordpressVersion}</span>
                  )}
                </td>
                <td>
                  {site.connectorVersion ? (
                    <span className="muted">v{site.connectorVersion}</span>
                  ) : (
                    <span className="muted">—</span>
                  )}
                </td>
                <td className="col-num">
                  {site.pluginUpdatesCount > 0 ? (
                    <span className="count count--warning"><Package size={12} />{site.pluginUpdatesCount}</span>
                  ) : (
                    <span className="muted">0</span>
                  )}
                </td>
                <td className="col-num">
                  {site.themeUpdatesCount > 0 ? (
                    <span className="count count--warning"><Palette size={12} />{site.themeUpdatesCount}</span>
                  ) : (
                    <span className="muted">0</span>
                  )}
                </td>
                <td className="col-num">
                  {site.totalUpdates > 0 ? (
                    <strong className="count--total">{site.totalUpdates}</strong>
                  ) : (
                    <span className="muted">0</span>
                  )}
                </td>
                <td className="muted">{relativeTime(site.lastScanAt)}</td>
                <td><StatusBadge status={site.status} /></td>
                <td className="col-actions">
                  <div className="row-actions">
                    <button
                      className="btn btn--xs btn--ghost"
                      onClick={() => scanSite(site.id)}
                      disabled={busy}
                      title="Scan now"
                    >
                      <RefreshCw size={13} className={site.status === 'scanning' ? 'spin' : ''} />
                    </button>
                    <button
                      className="btn btn--xs btn--primary"
                      onClick={() => onUpdateAll(site)}
                      disabled={busy || site.totalUpdates === 0}
                      title="Update all"
                    >
                      {site.status === 'updating' ? (
                        <>
                          <RefreshCw size={13} className="spin" /> Updating…
                        </>
                      ) : (
                        <>
                          <Zap size={13} /> Update All
                        </>
                      )}
                    </button>
                    <button
                      className="btn btn--xs btn--ghost"
                      onClick={() => openDrawer(site.id, true)}
                      title="Edit site"
                    >
                      <Pencil size={13} />
                    </button>
                    <button
                      className="btn btn--xs btn--danger"
                      onClick={() => onRemove(site)}
                      disabled={busy}
                      title="Remove site"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
