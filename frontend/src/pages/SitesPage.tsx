import { Plus, RefreshCw, Server } from 'lucide-react';
import { useState } from 'react';
import { useApp } from '../state/AppContext';
import { filterSitesByQuery } from '../state/selectors';
import { SitesTable } from '../components/SitesTable';
import { BulkActionBar } from '../components/BulkActionBar';
import { EmptyState } from '../components/EmptyState';

export function SitesPage() {
  const { state, scanAll, addSite } = useApp();
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ name: '', url: '', apiKey: '', group: '' });

  const sites = filterSitesByQuery(state.sites, state.search);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim() || !form.url.trim() || !form.apiKey.trim()) return;
    addSite({
      name: form.name.trim(),
      url: form.url.trim(),
      apiKey: form.apiKey.trim(),
      group: form.group.trim(),
    });
    setForm({ name: '', url: '', apiKey: '', group: '' });
    setShowAdd(false);
  };

  return (
    <div className="page">
      <div className="page__head">
        <div>
          <h1>Sites</h1>
          <p className="page__sub">{sites.length} of {state.sites.length} sites</p>
        </div>
        <div className="page__head-actions">
          <button className="btn btn--ghost" onClick={scanAll}><RefreshCw size={15} /> Scan all</button>
          <button className="btn btn--primary" onClick={() => setShowAdd((v) => !v)}><Plus size={15} /> Add site</button>
        </div>
      </div>

      {showAdd && (
        <form className="add-site-form card" onSubmit={submit}>
          <div className="field">
            <label>Name</label>
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="My WordPress site" autoFocus />
          </div>
          <div className="field">
            <label>URL</label>
            <input value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} placeholder="https://example.com" />
          </div>
          <div className="field">
            <label>API key</label>
            <input value={form.apiKey} onChange={(e) => setForm({ ...form, apiKey: e.target.value })} placeholder="WP Updater connector key" type="password" autoComplete="off" />
          </div>
          <div className="field">
            <label>Group</label>
            <input value={form.group} onChange={(e) => setForm({ ...form, group: e.target.value })} placeholder="Client A" />
          </div>
          <div className="add-site-form__actions">
            <button type="button" className="btn btn--ghost" onClick={() => setShowAdd(false)}>Cancel</button>
            <button type="submit" className="btn btn--primary">Add &amp; scan</button>
          </div>
        </form>
      )}

      {state.sites.length === 0 ? (
        <EmptyState
          icon={<Server size={28} />}
          title="No sites yet"
          description="Connect your first WordPress site to start monitoring updates."
          action={<button className="btn btn--primary" onClick={() => setShowAdd(true)}><Plus size={15} /> Add site</button>}
        />
      ) : sites.length === 0 ? (
        <EmptyState icon={<Server size={28} />} title="No matching sites" description={`No sites match "${state.search}".`} />
      ) : (
        <SitesTable sites={sites} />
      )}

      <BulkActionBar />
    </div>
  );
}
