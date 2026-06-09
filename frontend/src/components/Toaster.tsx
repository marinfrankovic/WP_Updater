import { CheckCircle2, Info, X, AlertTriangle, XCircle } from 'lucide-react';
import { useApp } from '../state/AppContext';
import type { Toast } from '../types';

const ICON = {
  success: CheckCircle2,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
};

export function Toaster() {
  const { state, dismissToast } = useApp();
  return (
    <div className="toaster" role="region" aria-live="polite">
      {state.toasts.map((t: Toast) => {
        const Icon = ICON[t.variant];
        return (
          <div key={t.id} className={`toast toast--${t.variant}`}>
            <Icon size={18} className="toast__icon" />
            <div className="toast__body">
              <strong>{t.title}</strong>
              {t.message && <span>{t.message}</span>}
            </div>
            <button className="toast__close" onClick={() => dismissToast(t.id)} aria-label="Dismiss">
              <X size={14} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
