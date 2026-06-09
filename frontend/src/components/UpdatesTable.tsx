import { ChevronDown, ChevronRight, Globe, Package, Palette, RefreshCw, Zap } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useApp } from '../state/AppContext';
import type { UpdateItem, UpdateType } from '../types';
import { StatusBadge } from './StatusBadge';
import { EmptyState } from './EmptyState';

type Tab = 'all' | UpdateType;

const TABS: { key: Tab; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'core', label: 'Core' },
  { key: 'plugin', label: 'Plugins' },
  { key: 'theme', label: 'Themes' },
];

const TYPE_ICON = {
  core: Globe,
  plugin: Package,
  theme: Palette,
};

export function UpdatesTable() {
  const {
    state,
    updateSite,
    updateItem,
    toggleUpdate,
    setUpdatesSelected,
    updateSelectedItems,
    setUpdatesTab,
    requestConfirm,
  } = useApp();
  const tab = state.updatesTab;
  const setTab = (t: Tab) => setUpdatesTab(t);
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  // Track which individual update item is currently being applied (UI progress).
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  // Track the sequential "Update selected" run for progress animation.
  const [selectedBusy, setSelectedBusy] = useState(false);

  const filtered = useMemo(
    () => state.updates.filter((u) => (tab === 'all' ? true : u.type === tab)),
    [state.updates, tab],
  );

  // Group remaining updates by site for readable, MainWP-style rows.
  const groups = useMemo(() => {
    const map = new Map<string, UpdateItem[]>();
    for (const u of filtered) {
      const arr = map.get(u.siteId) ?? [];
      arr.push(u);
      map.set(u.siteId, arr);
    }
    return Array.from(map.entries())
      .map(([siteId, items]) => ({
        site: state.sites.find((s) => s.id === siteId),
        items,
      }))
      .filter((g) => g.site)
      .sort((a, b) => b.items.length - a.items.length);
  }, [filtered, state.sites]);

  const counts = useMemo(
    () => ({
      all: state.updates.length,
      core: state.updates.filter((u) => u.type === 'core').length,
      plugin: state.updates.filter((u) => u.type === 'plugin').length,
      theme: state.updates.filter((u) => u.type === 'theme').length,
    }),
    [state.updates],
  );

  // Selection only counts items currently visible under the active tab.
  const selectedVisible = useMemo(() => filtered.filter((u) => u.selected), [filtered]);
  const allVisibleSelected = filtered.length > 0 && selectedVisible.length === filtered.length;

  const toggleSelectAllVisible = () => {
    setUpdatesSelected(
      filtered.map((u) => u.id),
      !allVisibleSelected,
    );
  };

  const runUpdateSelected = () => {
    requestConfirm({
      title: 'Update selected items',
      message: `Apply ${selectedVisible.length} selected update(s), one after another?`,
      confirmLabel: 'Update selected',
      onConfirm: async () => {
        if (selectedBusy) return;
        setSelectedBusy(true);
        try {
          await updateSelectedItems();
        } finally {
          setSelectedBusy(false);
        }
      },
    });
  };

  const runUpdateItem = (siteId: string, u: UpdateItem, siteName: string) => {
    requestConfirm({
      title: `Update ${u.name}`,
      message: `Apply this ${u.type} update on ${siteName}?`,
      confirmLabel: 'Update',
      onConfirm: async () => {
        if (updatingId) return;
        setUpdatingId(u.id);
        try {
          await updateItem(siteId, u.type, u.slug);
        } finally {
          setUpdatingId(null);
        }
      },
    });
  };

  return (
    <div className="updates-panel">
      <div className="updates-panel__bar">
        <div className="tabs">
          {TABS.map((t) => (
            <button
              key={t.key}
              className={`tab${tab === t.key ? ' is-active' : ''}`}
              onClick={() => setTab(t.key)}
            >
              {t.label}
              <span className="tab__count">{counts[t.key]}</span>
            </button>
          ))}
        </div>
        {filtered.length > 0 && (
          <div className="updates-panel__actions">
            <label className="select-all">
              <input type="checkbox" checked={allVisibleSelected} onChange={toggleSelectAllVisible} />
              Select all
            </label>
            <button
              className="btn btn--sm btn--primary"
              disabled={selectedVisible.length === 0 || selectedBusy}
              onClick={runUpdateSelected}
            >
              {selectedBusy ? (
                <>
                  <RefreshCw size={14} className="spin" /> Updating…
                </>
              ) : (
                <>
                  <Zap size={14} /> Update selected{selectedVisible.length ? ` (${selectedVisible.length})` : ''}
                </>
              )}
            </button>
          </div>
        )}
      </div>

      {groups.length === 0 ? (
        <EmptyState
          icon={<Zap size={28} />}
          title="No pending updates"
          description="Every monitored site is up to date for this filter."
        />
      ) : (
        <div className="update-groups">
          {groups.map(({ site, items }) => {
            if (!site) return null;
            const isCollapsed = collapsed[site.id];
            const scope: UpdateType | 'all' = tab;
            return (
              <div className="update-group" key={site.id}>
                <div className="update-group__head">
                  <button
                    className="update-group__toggle"
                    onClick={() => setCollapsed((c) => ({ ...c, [site.id]: !c[site.id] }))}
                  >
                    {isCollapsed ? <ChevronRight size={15} /> : <ChevronDown size={15} />}
                    <span className="update-group__name">{site.name}</span>
                    <span className="update-group__url">{site.url.replace(/^https?:\/\//, '')}</span>
                  </button>
                  <div className="update-group__right">
                    <span className="pill pill--neutral">{items.length} update(s)</span>
                    <button
                      className="btn btn--xs btn--primary"
                      disabled={site.status === 'updating'}
                      onClick={() =>
                        requestConfirm({
                          title: `Update ${site.name}`,
                          message: `Apply ${items.length} ${scope === 'all' ? '' : scope + ' '}update(s) on ${site.name}?`,
                          confirmLabel: 'Update',
                          onConfirm: () => updateSite(site.id, scope),
                        })
                      }
                    >
                      {site.status === 'updating' ? (
                        <>
                          <RefreshCw size={13} className="spin" /> Updating…
                        </>
                      ) : (
                        <>
                          <Zap size={13} /> Update {scope === 'all' ? 'all' : scope}
                        </>
                      )}
                    </button>
                  </div>
                </div>
                {!isCollapsed && (
                  <table className="data-table data-table--updates">
                    <tbody>
                      {items.map((u) => {
                        const Icon = TYPE_ICON[u.type];
                        return (
                          <tr key={u.id}>
                            <td className="col-check">
                              <input
                                type="checkbox"
                                checked={u.selected}
                                onChange={() => toggleUpdate(u.id)}
                                aria-label={`Select ${u.name}`}
                              />
                            </td>
                            <td className="col-type"><Icon size={13} /> <span className="muted">{u.type}</span></td>
                            <td className="col-name">{u.name}</td>
                            <td className="col-ver">
                              <code>{u.currentVersion}</code> → <code className="next">{u.availableVersion}</code>
                            </td>
                            <td className="col-status"><StatusBadge status={u.status} /></td>
                            <td className="col-action">
                              <button
                                className="btn btn--xs btn--ghost"
                                title={`Update ${u.name}`}
                                disabled={Boolean(updatingId)}
                                onClick={() => runUpdateItem(site.id, u, site.name)}
                              >
                                {updatingId === u.id ? (
                                  <>
                                    <RefreshCw size={12} className="spin" /> Updating…
                                  </>
                                ) : (
                                  <>
                                    <Zap size={12} /> Update
                                  </>
                                )}
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
