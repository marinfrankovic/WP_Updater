import { ExternalLink, PackageCheck } from 'lucide-react';
import { isVersionOlder } from '../lib/version';
import { useApp } from '../state/AppContext';

export function UpdateBanner() {
  const { appUpdate, setRoute, state, updateCheckEnabled } = useApp();
  if (!updateCheckEnabled || !appUpdate || appUpdate.error) return null;

  const outdatedConnectors = appUpdate.latestConnectorVersion
    ? state.sites.filter((site) => isVersionOlder(site.connectorVersion, appUpdate.latestConnectorVersion))
    : [];
  if (!appUpdate.updateAvailable && outdatedConnectors.length === 0) return null;

  const notices: string[] = [];
  if (appUpdate.updateAvailable) notices.push(`WP Updater v${appUpdate.latestVersion}`);
  if (outdatedConnectors.length > 0) {
    notices.push(
      `connector v${appUpdate.latestConnectorVersion} for ${outdatedConnectors.length} site${outdatedConnectors.length === 1 ? '' : 's'}`,
    );
  }

  return (
    <aside className="update-banner" aria-live="polite">
      <PackageCheck size={17} />
      <span><strong>Updates available:</strong> {notices.join(' and ')}</span>
      <button type="button" onClick={() => setRoute('settings')}>Review</button>
      {appUpdate.releaseUrl ? (
        <a href={appUpdate.releaseUrl} target="_blank" rel="noreferrer" title="Open release details">
          <ExternalLink size={15} />
        </a>
      ) : null}
    </aside>
  );
}