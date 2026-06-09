import { Activity } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useApp } from '../state/AppContext';
import { ActivityLogTable } from '../components/ActivityLogTable';
import { EmptyState } from '../components/EmptyState';
import type { ProgressStatus } from '../types';

type FilterKey = 'all' | 'success' | 'partial' | 'failed';

const FILTERS: { key: FilterKey; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'success', label: 'Success' },
  { key: 'partial', label: 'Partial' },
  { key: 'failed', label: 'Failed' },
];

export function ActivityLogPage() {
  const { state } = useApp();
  const [filter, setFilter] = useState<FilterKey>('all');

  const entries = useMemo(() => {
    if (filter === 'all') return state.activity;
    return state.activity.filter((a) => a.status === (filter as ProgressStatus));
  }, [state.activity, filter]);

  return (
    <div className="page">
      <div className="page__head">
        <div>
          <h1>Activity Log</h1>
          <p className="page__sub">{state.activity.length} recorded action(s)</p>
        </div>
        <div className="tabs tabs--inline">
          {FILTERS.map((f) => (
            <button key={f.key} className={`tab${filter === f.key ? ' is-active' : ''}`} onClick={() => setFilter(f.key)}>
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {entries.length === 0 ? (
        <EmptyState icon={<Activity size={28} />} title="No activity" description="No actions match this filter yet." />
      ) : (
        <ActivityLogTable entries={entries} />
      )}
    </div>
  );
}
