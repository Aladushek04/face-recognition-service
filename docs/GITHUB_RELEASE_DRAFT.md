# v1.0.3 — CPU default installer and GPU optional build

**Tag**: `v1.0.3`
**Target**: `main`

## Summary

v1.0.3 is a packaging and size optimization patch. The CPU installer is now the recommended default channel for most users, while the GPU installer remains available as an optional NVIDIA-accelerated build.

The existing v1.0.2 release remains unchanged.

## Downloads

Recommended:

* CPU installer: `FaceRecognitionService-Setup-v1.0.3-cpu.exe`
* CPU SHA256: pending final artifact build

Optional NVIDIA acceleration:

* GPU installer: `FaceRecognitionService-Setup-v1.0.3-gpu.exe`
* GPU SHA256: pending final artifact build

Portable packages are not planned as GitHub Release assets unless explicitly decided later.

## Which installer should I use?

Use the CPU installer unless you specifically want NVIDIA GPU acceleration. It is dramatically smaller and does not require CUDA or NVIDIA runtime files.

Use the GPU installer only on systems where NVIDIA acceleration is wanted. The bundled GPU build keeps CUDA provider support and should not require a separate CUDA Toolkit installation.

## Size improvements

Disposable test packaging measured:

* CPU installer: around 98 MiB.
* GPU installer: around 1.08 GiB.
* CPU portable ZIP: around 156 MiB.
* GPU portable ZIP: around 1.65 GiB.

The CPU installer is the default download because it is much smaller while preserving the normal desktop experience.

## CPU build

The CPU build is recommended for most users. It does not require CUDA, NVIDIA drivers, or NVIDIA provider runtime files.

Expected artifact name:

* `FaceRecognitionService-Setup-v1.0.3-cpu.exe`

## GPU build

The GPU build is optional and targets NVIDIA acceleration through ONNX Runtime CUDA provider support.

Expected artifact name:

* `FaceRecognitionService-Setup-v1.0.3-gpu.exe`

If a compatible NVIDIA GPU or driver is not available, the backend can fall back to CPU execution.

## Windows 11 requirement

Windows 11 is required. Windows 10 and older are not supported.

## WebView2 requirement

Microsoft Edge WebView2 Runtime is required to render the desktop UI. It is normally present on Windows 11, but the installer checks for it and prompts when required.

## Validation

Release preparation validation should include:

* Backend Python unittest suite.
* Docker offline smoke fixtures.
* Frontend Vitest suite and production build.
* WPF desktop build and xUnit tests.
* CPU and GPU installer dry-runs.
* CPU and GPU portable dry-runs.

Final SHA256 values must be filled only after final artifact build.

## Known notes

* MSIX is not planned.
* Portable packages remain supported locally/internal, but are not planned as GitHub Release assets unless explicitly decided later.
* The PyInstaller `passlib.handlers.bcrypt` hidden import warning is a stale P3 warning if `passlib` remains unused.
* TensorRT DLL warnings are P3 unless TensorRT provider support is explicitly promised. Do not add TensorRT packaging for this release.
