import { Globe, PencilLine, PlusCircle, RefreshCw, Zap } from 'lucide-react';

export function HelpPage() {
  return (
    <div className="page">
      <div className="page__head">
        <div>
          <h1>Help</h1>
          <p className="page__sub">How to add sites, manage and deploy updates</p>
        </div>
      </div>

      <section className="card settings-card settings-card--help">
        <h2>Getting started</h2>
        <p className="muted">A quick guide to connecting your WordPress sites and keeping them up to date.</p>

        <ol className="help-steps">
          <li className="help-step">
            <span className="help-step__icon"><Globe size={16} /></span>
            <div>
              <strong>1. Install the connector</strong>
              <p>
                Download <code>wp-updater-connector.php</code> from the{' '}
                <a
                  href="https://github.com/marinfrankovic/WP_Updater/releases"
                  target="_blank"
                  rel="noreferrer noopener"
                >
                  GitHub releases page
                </a>{' '}
                and drop it into each site's <code>wp-content/mu-plugins/</code> folder. Open{' '}
                <em>Settings → WP Updater</em> in wp-admin to copy that site's generated API key.
              </p>
            </div>
          </li>
          <li className="help-step">
            <span className="help-step__icon"><PlusCircle size={16} /></span>
            <div>
              <strong>2. Add a site</strong>
              <p>
                Go to the <em>Sites</em> page and choose <em>Add site</em>. Enter the site name, its URL and the API key
                from step 1. The dashboard scans it immediately and lists any available updates.
              </p>
            </div>
          </li>
          <li className="help-step">
            <span className="help-step__icon"><RefreshCw size={16} /></span>
            <div>
              <strong>3. Scan for updates</strong>
              <p>
                Use <em>Scan Now</em> in the top bar to refresh every site, or the scan button on an individual row. Each
                site shows pending core, plugin and theme counts. In addition to these manual scans, the dashboard runs an
                <em> automatic scan once a day</em> (06:00 by default) that re-checks every enabled site and emails a
                summary report. You can change the time — or turn the daily scan off — under <em>Settings → Scan schedule</em>.
              </p>
            </div>
          </li>
          <li className="help-step">
            <span className="help-step__icon"><Zap size={16} /></span>
            <div>
              <strong>4. Deploy updates</strong>
              <p>
                Update a single item, a whole site, or a scoped group (core / plugins / themes). On the
                {' '}<em>Updates</em> page you can tick several items and run <em>Update selected</em> — they apply one
                after another. Select multiple sites to bulk-update them from the top bar. A spinner shows while each
                update runs; results appear in the <em>Activity log</em>.
              </p>
            </div>
          </li>
          <li className="help-step">
            <span className="help-step__icon"><PencilLine size={16} /></span>
            <div>
              <strong>5. Open a site's side pane</strong>
              <p>
                On the <em>Sites</em> page (or the dashboard), click a site's name to slide open its <em>side pane</em> on
                the right. The pane shows that site's WP version, group, last scan/update times, an
                {' '}<em>auto-update</em> toggle, and its pending core, plugin and theme updates grouped together — so you
                can scan, update everything, or update a single item without leaving the pane. Click the
                {' '}<em>✕</em> (or anywhere outside it) to close.
              </p>
            </div>
          </li>
          <li className="help-step">
            <span className="help-step__icon"><PencilLine size={16} /></span>
            <div>
              <strong>6. Edit a site</strong>
              <p>
                To change a site's details, click the <em>pencil</em> icon on its row — this opens the side pane straight
                in <em>edit</em> mode. (If the pane is already open, use the pencil in its header.) Update the
                {' '}<em>name</em>, <em>URL</em>, <em>group</em> or <em>API key</em>, then <em>Save changes</em>; leave the
                API key blank to keep the current one. Use <em>Cancel</em> to discard. The <em>auto-update</em> toggle in
                the pane lets WordPress install updates on its own, and failed actions in the <em>Activity log</em> can be
                re-run with <em>Retry</em>.
              </p>
            </div>
          </li>
        </ol>

        <p className="muted help-note">
          Tip: updates always run sequentially (never in parallel) so a site is only ever applying one change at a time.
          Scans run on demand (manual) and automatically once a day; updates themselves are only ever applied manually —
          they are never installed by the scheduler.
        </p>
      </section>
    </div>
  );
}
