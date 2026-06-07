# v1.0.2 — Security, stability and test foundation update

**Tag**: `v1.0.2`  
**Target**: `main`

This patch release provides significant security hardening, robust safety optimizations, and complete test foundations for both desktop and frontend environments. It also finalizes our strict target OS policy by stripping outdated legacy compatibility layers.

## 1. Security hardening
* **WebView2 External Navigation**: Hardened the desktop shell to block external navigation, strictly limiting interactions to local boundaries.
* **Backend Host Binding**: Restricted backend API binding exclusively to `127.0.0.1` and added `TrustedHostMiddleware` protection.
* **Unsafe Job Arguments**: Hardened the Maintenance Job API to block execution of unsafe raw CLI arguments.

## 2. Stability and safety
* Cleaned up frontend React async test warnings for smoother UI stability.
* Eliminated noisy Pydantic V2 deprecation warnings in the backend logs.

## 3. Performance
* **Job List I/O Bound**: Significantly optimized maintenance job listing I/O by parsing only the latest 100 historical logs. This completely resolves CPU and disk spikes during heavy API polling.
* **Startup Delays**: Optimized desktop-to-backend startup wait boundaries for snappier loading times.

## 4. Testing and QA
* Added complete backend FastAPI TestClient route tests.
* Established a solid minimal frontend test foundation utilizing Vitest.
* Established a comprehensive desktop xUnit test foundation.

## 5. Developer workflow
* Integrated `docker-test.ps1` helper for running full offline Docker maintenance smoke fixtures, dramatically speeding up verification of indexing and job processing logic.

## 6. Windows 11 policy
* Explicitly dropped Windows 10 and older compatibility files and dependencies. Windows 11 is required.

## 7. Removed legacy items
* Removed obsolete standalone scripts (`start_service.py`, `scraper_ui.py`) and their batch wrappers. Their functionality is completely superseded by the desktop shell and modern maintenance jobs UI.

## 8. Validation
The codebase successfully passes all matrix tests:
* Python `unittest` suite (backend).
* `docker-test.ps1` (offline smoke fixtures).
* Vite build and `vitest` suite (frontend).
* `dotnet test` suite (WPF desktop shell).

## 9. Known notes
* **OS Support**: Windows 11 is required. Windows 10 and older are not supported.
* **WebView2**: Microsoft Edge WebView2 Runtime is required to launch the application.
* **Packaging**: Inno Setup installer and portable packages remain the supported distribution methods. MSIX remains cancelled and is not planned.
* Final installer/portable SHA256 checksums will be filled and published after artifact build.

---

### Artifacts (Pending Build)

* Installer: `FaceRecognitionService-Setup-v1.0.2-release.exe`
* Installer Checksum: `FaceRecognitionService-Setup-v1.0.2-release.sha256`
* Portable Archive: `FaceRecognitionService-Portable-v1.0.2-release.zip`
* Portable Checksum: `FaceRecognitionService-Portable-v1.0.2-release.sha256`
