# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules
import os
import sys

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
    "qasync",
    "PyQt6",
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
    "PyQt6.QtMultimedia",
    "PyQt6.QtMultimediaWidgets",
    "scripts",
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
    "qasync",
    "PyQt6",
]:
    datas += collect_data_files(package)

binaries = []
for package in [
    "cv2",
    "faiss",
    "onnxruntime",
    "PyQt6",
]:
    binaries += collect_dynamic_libs(package)

# Resolve nvidia.cudnn DLLs
import importlib.util
from pathlib import Path
cudnn_spec = importlib.util.find_spec("nvidia.cudnn")
if cudnn_spec and cudnn_spec.submodule_search_locations:
    cudnn_bin = Path(cudnn_spec.submodule_search_locations[0]) / "bin"
    if cudnn_bin.exists():
        for dll in cudnn_bin.glob("*.dll"):
            binaries.append((str(dll), "."))

a = Analysis(
    ["desktop_pyqt/main.py"],
    pathex=[".", "desktop_pyqt", "backend"],
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

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FaceRecognitionService",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Windowed GUI application, no console popup
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="desktop/electron/assets/app-icon.ico" if os.path.exists("desktop/electron/assets/app-icon.ico") else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="FaceRecognitionService",
)
