# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules


hiddenimports = []
for package in [
    "aiofiles",
    "cv2",
    "faiss",
    "fastapi",
    "filetype",
    "insightface",
    "onnxruntime",
    "pydantic",
    "pydantic_settings",
    "uvicorn",
]:
    hiddenimports += collect_submodules(package)

datas = []
for package in [
    "cv2",
    "fastapi",
    "insightface",
    "onnxruntime",
    "pydantic",
    "pydantic_settings",
    "uvicorn",
]:
    datas += collect_data_files(package)

binaries = []
for package in [
    "cv2",
    "faiss",
    "onnxruntime",
]:
    binaries += collect_dynamic_libs(package)

# Portable MVP runs with CPUExecutionProvider by default. Do not ship partial
# CUDA/TensorRT provider DLLs without their external NVIDIA dependencies.
binaries = [
    item
    for item in binaries
    if "onnxruntime_providers_cuda" not in str(item).lower()
    and "onnxruntime_providers_tensorrt" not in str(item).lower()
]
datas = [
    item
    for item in datas
    if "onnxruntime_providers_cuda" not in str(item).lower()
    and "onnxruntime_providers_tensorrt" not in str(item).lower()
]


a = Analysis(
    ["desktop_backend.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "notebook",
        "pytest",
        "tkinter",
    ],
    noarchive=False,
    optimize=0,
)
a.binaries = [
    item
    for item in a.binaries
    if "onnxruntime_providers_cuda" not in str(item).lower()
    and "onnxruntime_providers_tensorrt" not in str(item).lower()
]
a.datas = [
    item
    for item in a.datas
    if "onnxruntime_providers_cuda" not in str(item).lower()
    and "onnxruntime_providers_tensorrt" not in str(item).lower()
]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="backend",
)
