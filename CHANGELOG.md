# Changelog

All notable changes to this project will be documented in this file.

## [v1.0.0] - 2026-06-06

### Added
- **Installer**: Automated standalone Inno Setup installer.
- **Desktop Shell**: Embedded Microsoft Edge WebView2 WPF desktop shell.
- **Backend Runtime**: Hidden PyInstaller-packaged FastAPI backend supporting both CUDA GPU and CPU fallback without requiring external Python environments.
- **Setup Mode**: Safe first-run defaults requiring explicit manual path configuration upon fresh installation.
- **Configuration Persistence**: `config.json` is safely preserved during upgrades, while `config.example.json` is automatically refreshed.
- **Maintenance Center**: In-app UI for managing FAISS indexing, actor/image cleanup, and StashDB backfills as background jobs.
- **Local Logs & Jobs**: Application logs and job metadata safely stored in `%LOCALAPPDATA%\Programs\Face Recognition Service`.

### Changed
- Refactored frontend to support dynamic path missing validations via `Configuration Required` state.
- Transitioned project architecture completely away from Electron/PyQt towards WPF and FastAPI.

### Fixed
- Backend and Python processes cleanly exit when the desktop UI is closed, ensuring no orphaned background tasks.
- Resolved installer access errors by replacing default `D:\` drives with safe empty paths in the bundled template.
