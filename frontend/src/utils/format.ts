import type { ActivityAction, ProgressStatus, UpdateItemStatus } from '../types';

/** Human-friendly relative time, e.g. "18m ago", "2h ago", "3d ago". */
export function relativeTime(iso: string | null): string {
  if (!iso) return 'never';
  const diff = Date.now() - new Date(iso).getTime();
  const sec = Math.round(diff / 1000);
  if (sec < 60) return `${sec}s ago`;
  const min = Math.round(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.round(hr / 24);
  if (day < 30) return `${day}d ago`;
  const mon = Math.round(day / 30);
  return `${mon}mo ago`;
}

/** Format a duration in ms as "4.2s" or "1m 03s". */
export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  const sec = ms / 1000;
  if (sec < 60) return `${sec.toFixed(1)}s`;
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return `${m}m ${s.toString().padStart(2, '0')}s`;
}

export function statusLabel(status: ProgressStatus | UpdateItemStatus): string {
  switch (status) {
    case 'idle':
      return 'Idle';
    case 'scanning':
      return 'Scanning';
    case 'updating':
      return 'Updating';
    case 'success':
      return 'Success';
    case 'failed':
      return 'Failed';
    case 'partial':
      return 'Partial';
    case 'available':
      return 'Available';
    case 'up-to-date':
      return 'Up to date';
    default:
      return status;
  }
}

export function actionLabel(action: ActivityAction): string {
  switch (action) {
    case 'scan':
      return 'Scan';
    case 'update-core':
      return 'Update core';
    case 'update-plugins':
      return 'Update plugins';
    case 'update-themes':
      return 'Update themes';
    case 'update-all':
      return 'Update all';
    default:
      return action;
  }
}
