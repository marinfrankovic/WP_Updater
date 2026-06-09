import { useApp } from '../state/AppContext';
import { UpdatesTable } from '../components/UpdatesTable';

export function UpdatesPage() {
  const { state } = useApp();
  const total = state.updates.length;

  return (
    <div className="page">
      <div className="page__head">
        <div>
          <h1>Updates</h1>
          <p className="page__sub">{total} pending update(s) across all sites</p>
        </div>
      </div>
      <UpdatesTable />
    </div>
  );
}
