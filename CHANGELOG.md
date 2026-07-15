# Changelog

## 1.8.0 - 2026-07-15

### Added

- Added opt-in update checks when the dashboard opens and every 24 hours while it remains open.
- Added a compact dashboard-wide banner for available dashboard and MU connector updates.
- Added release-asset connector version discovery and per-site installed-version comparison.
- Added connector download details and affected site names to Application updates.

### Security

- Kept all checks informational. WP Updater does not download images, change WordPress files, access Docker, or execute update commands.

## 1.7.0 - 2026-07-15

### Added

- Added installed-version information and manual stable-release checks under Settings.
- Added an optional browser-local check when Settings opens, disabled until the user opts in.
- Added release notes, release links, and copyable commands for Docker Hub and local source-build deployments.
- Added a pinned pytest framework with update-check regression tests.
- Added GitHub Actions checks for backend tests and the production React build.

### Security

- Kept application updates informational and manual. The dashboard cannot access Docker, download images, or execute update commands.

### Fixed

- Forced LF line endings for shell scripts so source archives deploy correctly from Windows workstations.