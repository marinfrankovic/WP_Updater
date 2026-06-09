import { Moon, RefreshCw, Search, Sun, Zap } from 'lucide-react';
import { useState } from 'react';
import { useApp } from '../state/AppContext';

export function Topbar() {
  const { state, setSearch, toggleTheme, scanAll, bulkUpdate, requestConfirm } = useApp();
  const selected = state.sites.filter((s) => s.selected);
  const [updating, setUpdating] = useState(false);

  const onUpdateSelected = () => {
    if (selected.length === 0) return;
    const ids = selected.map((s) => s.id);
    requestConfirm({
      title: 'Update selected sites',
      message: `Run "update all" on ${selected.length} selected site(s)? This updates core, plugins and themes where updates are available.`,
      confirmLabel: 'Update all',
      onConfirm: async () => {
        if (updating) return;
        setUpdating(true);
        try {
          await bulkUpdate(ids, 'all');
        } finally {
          setUpdating(false);
        }
      },
    });
  };

  return (
    <header className="topbar">
      <div className="topbar__search">
        <Search size={16} />
        <input
          type="search"
          placeholder="Search sites, URLs, groups…"
          value={state.search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Global search"
        />
      </div>

      <div className="topbar__actions">
        <button className="btn btn--ghost" onClick={scanAll}>
          <RefreshCw size={15} />
          Scan Now
        </button>
        <button
          className="btn btn--primary"
          onClick={onUpdateSelected}
          disabled={selected.length === 0 || updating}
        >
          {updating ? (
            <>
              <RefreshCw size={15} className="spin" />
              Updating…
            </>
          ) : (
            <>
              <Zap size={15} />
              Update Selected
              {selected.length > 0 && <span className="btn__count">{selected.length}</span>}
            </>
          )}
        </button>
        <button
          className="btn btn--icon"
          onClick={toggleTheme}
          aria-label="Toggle theme"
          title={state.theme === 'dark' ? 'Switch to light' : 'Switch to dark'}
        >
          {state.theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
        </button>
      </div>
    </header>
  );
}
