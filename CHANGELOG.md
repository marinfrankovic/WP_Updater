# Changelog

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