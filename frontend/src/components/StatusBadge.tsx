import type { ProgressStatus, UpdateItemStatus } from '../types';
import { statusLabel } from '../utils/format';

type AnyStatus = ProgressStatus | UpdateItemStatus;

// Maps every status to a semantic colour class:
//   green = success/up-to-date, amber = available/partial/scanning,
//   red = failed, blue = updating, neutral = idle.
const TONE: Record<AnyStatus, string> = {
  idle: 'neutral',
  scanning: 'info',
  updating: 'info',
  success: 'success',
  failed: 'danger',
  partial: 'warning',
  available: 'warning',
  'up-to-date': 'success',
};

export function StatusBadge({ status }: { status: AnyStatus }) {
  const tone = TONE[status] ?? 'neutral';
  const animated = status === 'scanning' || status === 'updating';
  return (
    <span className={`badge badge--${tone}${animated ? ' badge--pulse' : ''}`}>
      {animated && <span className="badge-dot" />}
      {statusLabel(status)}
    </span>
  );
}
