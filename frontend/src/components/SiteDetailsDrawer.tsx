import { Globe, Package, Palette, Pencil, RefreshCw, Trash2, X, Zap } from 'lucide-react';
import { useEffect, useState, type ReactNode } from 'react';
import { useApp } from '../state/AppContext';
import type { UpdateItem } from '../types';
import { relativeTime } from '../utils/format';
import { StatusBadge } from './StatusBadge';

export function SiteDetailsDrawer() {
  const { state, closeDrawer, scanSite, updateSite, updateItem, removeSite, requestConfirm, setAutoUpdate, editSite } =
    useApp();
  const site = state.sites.find((s) => s.id === state.drawerSiteId) ?? null;
  const open = Boolean(site);

  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ name: '', url: '', apiKey: '', group: '' });
  // Track which individual update item is currently being applied (UI progress).
  const [updatingSlug, setUpdatingSlug] = useState<string | null>(null);

  // Reset edit/progress UI whenever the drawer target changes or closes.
  // Honour the drawerEdit flag so opening via the table pencil starts in edit mode.
  useEffect(() => {
    setEditing(state.drawerEdit && Boolean(site));
    setUpdatingSlug(null);
    if (state.drawerEdit && site) {
      setForm({ name: site.name, url: site.url, apiKey: '', group: site.group });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [site?.id, state.drawerEdit]);

  const items = site ? state.updates.filter((u) => u.siteId === site.id) : [];
  const core = items.filter((u) => u.type === 'core');
  const plugins = items.filter((u) => u.type === 'plugin');
  const themes = items.filter((u) => u.type === 'theme');

  const onUpdateAll = () => {
    if (!site || site.totalUpdates === 0) return;
    requestConfirm({
      title: `Update ${site.name}`,
      message: `Apply all ${site.totalUpdates} available update(s) on ${site.name}?`,
      confirmLabel: 'Update all',
      onConfirm: () => updateSite(site.id, 'all'),
    });
  };

  const onUpdateItem = async (u: UpdateItem) => {
    if (!site || updatingSlug) return;
    setUpdatingSlug(u.id);
    try {
      await updateItem(site.id, u.type, u.slug);
    } finally {
      setUpdatingSlug(null);
    }
  };

  const onRemove = () => {
    if (!site) return;
    requestConfirm({
      title: `Remove ${site.name}`,
      message: `Remove ${site.name} from WP Updater? This deletes its stored scan history here but does not change the WordPress site itself.`,
      confirmLabel: 'Remove site',
      onConfirm: () => removeSite(site.id),
    });
  };

  const startEdit = () => {
    if (!site) return;
    setForm({ name: site.name, url: site.url, apiKey: '', group: site.group });
    setEditing(true);
  };

  const submitEdit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!site) return;
    const patch: { name?: string; url?: string; apiKey?: string; group?: string } = {};
    if (form.name.trim() && form.name.trim() !== site.name) patch.name = form.name.trim();
    if (form.url.trim() && form.url.trim() !== site.url) patch.url = form.url.trim();
    if (form.group.trim() !== site.group) patch.group = form.group.trim();
    if (form.apiKey.trim()) patch.apiKey = form.apiKey.trim();
    if (Object.keys(patch).length > 0) editSite(site.id, patch);
    setEditing(false);
  };

  const busy = site?.status === 'scanning' || site?.status === 'updating' || Boolean(updatingSlug);

  return (
    <>
      <div className={`drawer-scrim${open ? ' is-open' : ''}`} onClick={closeDrawer} />
      <aside className={`drawer${open ? ' is-open' : ''}`} aria-hidden={!open}>
        {site && (
          <>
            <header className="drawer__head">
              <div>
                <h2>{site.name}</h2>
                <a href={site.url} target="_blank" rel="noreferrer" className="drawer__url">
                  {site.url.replace(/^https?:\/\//, '')}
                </a>
              </div>
              <div className="drawer__head-actions">
                <button className="btn btn--icon" onClick={startEdit} aria-label="Edit site" title="Edit site">
                  <Pencil size={15} />
                </button>
                <button className="btn btn--icon" onClick={closeDrawer} aria-label="Close">
                  <X size={16} />
                </button>
              </div>
            </header>

            {editing ? (
              <form className="drawer__edit" onSubmit={submitEdit}>
                <div className="field">
                  <label>Name</label>
                  <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} autoFocus />
                </div>
                <div className="field">
                  <label>URL</label>
                  <input value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} />
                </div>
                <div className="field">
                  <label>Group</label>
                  <input value={form.group} onChange={(e) => setForm({ ...form, group: e.target.value })} />
                </div>
                <div className="field">
                  <label>API key <span className="muted">(leave blank to keep current)</span></label>
                  <input
                    value={form.apiKey}
                    onChange={(e) => setForm({ ...form, apiKey: e.target.value })}
                    type="password"
                    autoComplete="off"
                    placeholder="••••••••"
                  />
                </div>
                <div className="drawer__edit-actions">
                  <button type="button" className="btn btn--ghost btn--sm" onClick={() => setEditing(false)}>
                    Cancel
                  </button>
                  <button type="submit" className="btn btn--primary btn--sm">Save changes</button>
                </div>
              </form>
            ) : (
              <>
                <div className="drawer__meta">
                  <div><span className="muted">WP version</span><strong>{site.wordpressVersion}</strong></div>
                  <div><span className="muted">Group</span><strong>{site.group}</strong></div>
                  <div><span className="muted">Status</span><StatusBadge status={site.status} /></div>
                  <div><span className="muted">Last scan</span><strong>{relativeTime(site.lastScanAt)}</strong></div>
                  <div><span className="muted">Last update</span><strong>{relativeTime(site.lastUpdatedAt)}</strong></div>
                  <div><span className="muted">Total updates</span><strong>{site.totalUpdates}</strong></div>
                </div>

                <label className="drawer__toggle">
                  <input
                    type="checkbox"
                    checked={site.autoUpdate}
                    onChange={(e) => setAutoUpdate(site.id, e.target.checked)}
                  />
                  <span>
                    <strong>Auto-update</strong>
                    <span className="muted">Let WordPress auto-install plugin &amp; theme updates on this site.</span>
                  </span>
                </label>

                <label className="drawer__toggle">
                  <input
                    type="checkbox"
                    checked={site.notifyAdmin}
                    onChange={(e) => editSite(site.id, { notifyAdmin: e.target.checked })}
                  />
                  <span>
                    <strong>Email this site's admin</strong>
                    <span className="muted">Include this site's WordPress admin address in update report emails.</span>
                  </span>
                </label>

                <label className="drawer__toggle">
                  <input
                    type="checkbox"
                    checked={site.notifyTelegram}
                    onChange={(e) => editSite(site.id, { notifyTelegram: e.target.checked })}
                  />
                  <span>
                    <strong>Telegram alerts</strong>
                    <span className="muted">Flag this site for Telegram update notifications.</span>
                  </span>
                </label>

                <div className="drawer__actions">
                  <button className="btn btn--ghost btn--sm" onClick={() => scanSite(site.id)} disabled={busy}>
                    <RefreshCw size={14} className={site.status === 'scanning' ? 'spin' : ''} /> Scan
                  </button>
                  <button className="btn btn--primary btn--sm" onClick={onUpdateAll} disabled={busy || site.totalUpdates === 0}>
                    {site.status === 'updating' ? (
                      <>
                        <RefreshCw size={14} className="spin" /> Updating…
                      </>
                    ) : (
                      <>
                        <Zap size={14} /> Update all
                      </>
                    )}
                  </button>
                  <button className="btn btn--danger btn--sm" onClick={onRemove} title="Remove site" disabled={busy}>
                    <Trash2 size={14} /> Remove
                  </button>
                </div>

                <div className="drawer__body">
                  <DrawerGroup
                    title="WordPress Core"
                    icon={<Globe size={14} />}
                    items={core}
                    emptyText="Core is up to date."
                    onUpdateGroup={core.length ? () => updateSite(site.id, 'core') : undefined}
                    onUpdateItem={onUpdateItem}
                    updatingId={updatingSlug}
                    anyBusy={busy}
                    groupBusy={site.status === 'updating'}
                  />
                  <DrawerGroup
                    title="Plugins"
                    icon={<Package size={14} />}
                    items={plugins}
                    emptyText="All plugins up to date."
                    onUpdateGroup={plugins.length ? () => updateSite(site.id, 'plugin') : undefined}
                    onUpdateItem={onUpdateItem}
                    updatingId={updatingSlug}
                    anyBusy={busy}
                    groupBusy={site.status === 'updating'}
                  />
                  <DrawerGroup
                    title="Themes"
                    icon={<Palette size={14} />}
                    items={themes}
                    emptyText="All themes up to date."
                    onUpdateGroup={themes.length ? () => updateSite(site.id, 'theme') : undefined}
                    onUpdateItem={onUpdateItem}
                    updatingId={updatingSlug}
                    anyBusy={busy}
                    groupBusy={site.status === 'updating'}
                  />
                </div>
              </>
            )}
          </>
        )}
      </aside>
    </>
  );
}

function DrawerGroup({
  title,
  icon,
  items,
  emptyText,
  onUpdateGroup,
  onUpdateItem,
  updatingId,
  anyBusy,
  groupBusy,
}: {
  title: string;
  icon: ReactNode;
  items: UpdateItem[];
  emptyText: string;
  onUpdateGroup?: () => void;
  onUpdateItem: (u: UpdateItem) => void;
  updatingId: string | null;
  anyBusy: boolean;
  groupBusy: boolean;
}) {
  return (
    <section className="drawer-group">
      <div className="drawer-group__head">
        <span className="drawer-group__title">{icon} {title}</span>
        {items.length > 0 && (
          <button className="btn btn--xs btn--ghost" onClick={onUpdateGroup} disabled={anyBusy}>
            {groupBusy ? (
              <>
                <RefreshCw size={12} className="spin" /> Updating…
              </>
            ) : (
              <>Update all ({items.length})</>
            )}
          </button>
        )}
      </div>
      {items.length === 0 ? (
        <p className="drawer-group__empty">{emptyText}</p>
      ) : (
        <ul className="drawer-group__list">
          {items.map((u) => {
            const isUpdating = updatingId === u.id;
            return (
              <li key={u.id}>
                <span className="drawer-item__name">{u.name}</span>
                <span className="drawer-item__ver">
                  <code>{u.currentVersion}</code> → <code className="next">{u.availableVersion}</code>
                </span>
                <button
                  className="btn btn--xs btn--primary"
                  onClick={() => onUpdateItem(u)}
                  disabled={anyBusy}
                  title={`Update ${u.name}`}
                >
                  {isUpdating ? (
                    <>
                      <RefreshCw size={12} className="spin" /> Updating…
                    </>
                  ) : (
                    <>
                      <Zap size={12} /> Update
                    </>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
