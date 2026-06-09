import { AlertTriangle } from 'lucide-react';
import { useApp } from '../state/AppContext';

export function ConfirmModal() {
  const { state, closeConfirm } = useApp();
  const confirm = state.confirm;
  if (!confirm) return null;

  return (
    <div className="modal-overlay" onClick={closeConfirm}>
      <div className="modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
        <div className="modal__head">
          <span className="modal__icon"><AlertTriangle size={20} /></span>
          <h2>{confirm.title}</h2>
        </div>
        <p className="modal__message">{confirm.message}</p>
        <div className="modal__actions">
          <button className="btn btn--ghost" onClick={closeConfirm}>Cancel</button>
          <button
            className="btn btn--primary"
            onClick={() => {
              confirm.onConfirm();
              closeConfirm();
            }}
          >
            {confirm.confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
