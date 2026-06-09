import { X, Zap } from 'lucide-react';
import { useApp } from '../state/AppContext';
import type { UpdateType } from '../types';

// Sticky bar shown when one or more sites are selected. Offers scoped bulk
// updates (core / plugins / themes / everything) across the selection.
export function BulkActionBar() {
  const { state, clearSiteSelection, bulkUpdate, requestConfirm } = useApp();
  const selected = state.sites.filter((s) => s.selected);
  if (selected.length === 0) return null;

  const ids = selected.map((s) => s.id);
  const run = (scope: UpdateType | 'all', label: string) =>
    requestConfirm({
      title: `${label} · ${selected.length} site(s)`,
      message: `Run "${label}" on ${selected.length} selected site(s)? Only sites with matching available updates are affected.`,
      confirmLabel: label,
      onConfirm: () => bulkUpdate(ids, scope),
    });

  return (
    <div className="bulk-bar">
      <div className="bulk-bar__info">
        <span className="bulk-bar__count">{selected.length}</span>
        site(s) selected
        <button className="bulk-bar__clear" onClick={clearSiteSelection}>
          <X size={13} /> Clear
        </button>
      </div>
      <div className="bulk-bar__actions">
        <button className="btn btn--sm btn--ghost" onClick={() => run('core', 'Update core')}>Core</button>
        <button className="btn btn--sm btn--ghost" onClick={() => run('plugin', 'Update plugins')}>Plugins</button>
        <button className="btn btn--sm btn--ghost" onClick={() => run('theme', 'Update themes')}>Themes</button>
        <button className="btn btn--sm btn--primary" onClick={() => run('all', 'Update everything')}>
          <Zap size={14} /> Update everything
        </button>
      </div>
    </div>
  );
}
