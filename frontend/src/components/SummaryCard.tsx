import type { ReactNode } from 'react';

interface SummaryCardProps {
  label: string;
  value: number | string;
  icon: ReactNode;
  tone?: 'neutral' | 'success' | 'warning' | 'danger' | 'info';
  hint?: string;
  onClick?: () => void;
}

export function SummaryCard({ label, value, icon, tone = 'neutral', hint, onClick }: SummaryCardProps) {
  const Tag = onClick ? 'button' : 'div';
  return (
    <Tag className={`summary-card summary-card--${tone}${onClick ? ' summary-card--clickable' : ''}`} onClick={onClick}>
      <div className="summary-card__icon">{icon}</div>
      <div className="summary-card__body">
        <div className="summary-card__value">{value}</div>
        <div className="summary-card__label">{label}</div>
        {hint && <div className="summary-card__hint">{hint}</div>}
      </div>
    </Tag>
  );
}
