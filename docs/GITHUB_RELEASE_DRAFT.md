# Face Recognition Service v1.0.0 (First Stable Release)

This is the first stable release of the Face Recognition Service. It provides local offline face recognition and actor matching using InsightFace, FAISS, and a standalone desktop React UI.

## 🚀 Key Features
- **Local Desktop UI**: Embedded Chromium shell via WebView2.
- **Offline ML**: Bundled hidden PyInstaller FastAPI backend with GPU (CUDA) and CPU support.
- **Smart Directory Management**: Writable configurations, jobs, and logs are kept in safe local paths, while massive ML data and video files reside on user-defined drives.
- **Safe Setup Mode**: Installer starts the app with safe, empty defaults that require manual first-run configuration.
- **Maintenance Center**: In-app UI for managing FAISS indexing, actor/image cleanup, and StashDB backfills as background jobs.

## 📦 File Hashes
* **Validated Release Candidate**: `FaceRecognitionService-Setup-v1.0.0-813c65e.exe`
* **SHA256**: `74EF6EA76BECD58EB54E420D2AFE9163A7EA5AC4E6247358E6856179FCC4E814`

*(Note: The final public GitHub release file may be renamed to `FaceRecognitionService-Setup-v1.0.0.exe` providing it is an exact byte-for-byte copy with a confirmed SHA256 match).*

## 💻 System Requirements
1. **Microsoft .NET 10 Desktop Runtime (x64)** (The installer will prompt you if missing).
2. **Microsoft Edge WebView2 Runtime** (Pre-installed on Windows 11; installer will prompt if missing).
3. **NVIDIA GPU (Optional)**: Automatically falls back to CPU if a CUDA GPU is not available. No separate CUDA Toolkit installation is required.

## 📥 Installation Steps
1. Download the validated installer `FaceRecognitionService-Setup-v1.0.0-813c65e.exe`.
2. Run the executable to install the application. It will install automatically to `%LOCALAPPDATA%\Programs\Face Recognition Service`.
3. Launch "Face Recognition Service" from your Start Menu.
4. On your very first run, you will see a **Configuration Required** screen.

## ⚙️ First-Run Setup Steps
1. Open the **Settings** menu.
2. Configure your external data directories. Expected production paths:
   - Base Directory: `D:\FaceService`
   - Actors Directory: `D:\FaceService\actors`
   - Models Directory: `D:\FaceService\models`
   - FAISS Index Directory: `D:\FaceService\data\faiss_index`
   - Videos Directory: `D:\Videos`
3. Click **Validate**. If validation succeeds, click **Save** and restart the app when prompted.
4. The backend should successfully load and display: `Model Ready`, indicating the AI has initialized.

## 🔄 Upgrades & Uninstallation
- **Upgrades**: `config.json` is safely preserved during reinstalls/upgrades. `config.example.json` is automatically refreshed to ensure you have the latest template schema.
- **Uninstallation**: Uninstalling via the Windows Control Panel removes the program files. Your `config.json`, logs, and external ML models/videos are completely safe and untouched.

## ⚠️ Known Issues
- **Jobs UI Delay**: The Job Status UI can briefly display `FAILED` before updating to `COMPLETED` for long-running dry-run tasks.
- **Validation Message**: If an external path is missing, the Settings validation message simply says "Base directory not found at " rather than explicitly stating it is unconfigured.
- **StashDB API Warning**: You may see a `StashDB API key is not configured` warning. This is purely optional and non-blocking unless you intend to scrape actor profiles.

## 🧪 Validated Test Matrix
| Scenario | Result | Notes |
|----------|--------|-------|
| Clean Windows 11 VM | **PASSED** | App correctly starts in Setup Mode with safe empty defaults. |
| Configured Hardware (GPU) | **PASSED** | Correctly hooks to external drives, initializes CUDA models, and FAISS vector matching functions accurately. |
| Process Lifecycle | **PASSED** | No orphaned `python.exe` or `FaceBackend.exe` remains after UI closure. |
