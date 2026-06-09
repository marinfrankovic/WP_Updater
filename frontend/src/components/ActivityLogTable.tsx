import { ChevronDown, ChevronRight, RefreshCw, RotateCcw } from 'lucide-react';
import { Fragment, useState } from 'react';
import { useApp } from '../state/AppContext';
import type { ActivityLogEntry } from '../types';
import { actionLabel, formatDuration, relativeTime } from '../utils/format';
import { StatusBadge } from './StatusBadge';

export function ActivityLogTable({ entries }: { entries: ActivityLogEntry[] }) {
  const { state, retryActivity } = useApp();
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  return (
    <div className="card">
      <table className="data-table data-table--activity">
        <thead>
          <tr>
            <th className="col-expand" />
            <th>Time</th>
            <th>Site</th>
            <th>Action</th>
            <th>Status</th>
            <th className="col-num">Duration</th>
            <th className="col-actions">Actions</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => {
            const open = expanded[entry.id];
            const hasDetails = Boolean(entry.details?.length || entry.error);
            const failed = entry.status === 'failed' || entry.status === 'partial';
            return (
              <Fragment key={entry.id}>
                <tr className={failed ? 'row--alert' : ''}>
                  <td className="col-expand">
                    {hasDetails && (
                      <button
                        className="icon-btn"
                        onClick={() => setExpanded((e) => ({ ...e, [entry.id]: !e[entry.id] }))}
                        aria-label="Toggle details"
                      >
                        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                      </button>
                    )}
                  </td>
                  <td className="muted" title={new Date(entry.timestamp).toLocaleString()}>
                    {relativeTime(entry.timestamp)}
                  </td>
                  <td><strong>{entry.siteName}</strong></td>
                  <td>{actionLabel(entry.action)}</td>
                  <td><StatusBadge status={entry.status} /></td>
                  <td className="col-num muted">{entry.durationMs ? formatDuration(entry.durationMs) : '—'}</td>
                  <td className="col-actions">
                    {failed && (() => {
                      const retrying = Boolean(
                        entry.siteId &&
                          state.sites.find((s) => s.id === entry.siteId)?.status === 'updating',
                      );
                      return (
                        <button
                          className="btn btn--xs btn--ghost"
                          onClick={() => retryActivity(entry.id)}
                          disabled={retrying}
                        >
                          {retrying ? (
                            <>
                              <RefreshCw size={13} className="spin" /> Updating…
                            </>
                          ) : (
                            <>
                              <RotateCcw size={13} /> Retry
                            </>
                          )}
                        </button>
                      );
                    })()}
                  </td>
                </tr>
                {open && hasDetails && (
                  <tr className="detail-row" key={`${entry.id}-detail`}>
                    <td />
                    <td colSpan={6}>
                      {entry.error && <p className="detail-error">{entry.error}</p>}
                      {entry.details && entry.details.length > 0 && (
                        <ul className="detail-list">
                          {entry.details.map((d, i) => (
                            <li key={i} className={d.result === 'failed' ? 'is-failed' : 'is-ok'}>
                              <span className="detail-list__name">{d.name}</span>
                              <StatusBadge status={d.result === 'failed' ? 'failed' : 'success'} />
                              {d.message && <span className="detail-list__msg">{d.message}</span>}
                            </li>
                          ))}
                        </ul>
                      )}
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
