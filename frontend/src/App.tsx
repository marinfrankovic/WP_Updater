import { useApp } from './state/AppContext';
import { Sidebar } from './components/Sidebar';
import { Topbar } from './components/Topbar';
import { Toaster } from './components/Toaster';
import { ConfirmModal } from './components/ConfirmModal';
import { SiteDetailsDrawer } from './components/SiteDetailsDrawer';
import { SkeletonTable } from './components/Skeleton';
import { UpdateBanner } from './components/UpdateBanner';
import { DashboardPage } from './pages/DashboardPage';
import { SitesPage } from './pages/SitesPage';
import { UpdatesPage } from './pages/UpdatesPage';
import { ActivityLogPage } from './pages/ActivityLogPage';
import { SettingsPage } from './pages/SettingsPage';
import { HelpPage } from './pages/HelpPage';

export function App() {
  const { state } = useApp();

  const renderPage = () => {
    switch (state.route) {
      case 'dashboard':
        return <DashboardPage />;
      case 'sites':
        return <SitesPage />;
      case 'updates':
        return <UpdatesPage />;
      case 'activity':
        return <ActivityLogPage />;
      case 'settings':
        return <SettingsPage />;
      case 'help':
        return <HelpPage />;
      default:
        return <DashboardPage />;
    }
  };

  return (
    <div className="app-shell">
      <Sidebar />
      <div className="app-main">
        <Topbar />
        <UpdateBanner />
        <main className="app-content">
          {state.loading ? (
            <div className="page">
              <div className="page__head"><h1>Loading…</h1></div>
              <SkeletonTable />
            </div>
          ) : (
            renderPage()
          )}
        </main>
      </div>
      <SiteDetailsDrawer />
      <ConfirmModal />
      <Toaster />
    </div>
  );
}
