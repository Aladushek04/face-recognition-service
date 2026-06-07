# -*- mode: python ; coding: utf-8 -*-

import os
import glob

# Resolve DLLs
site_packages = r'C:\Users\isoko\AppData\Local\Programs\Python\Python310\lib\site-packages'
required_dlls = [
    'cudnn64_9.dll',
    'cudnn_engines_runtime_compiled64_9.dll',
    'cudnn_engines_precompiled64_9.dll',
    'cudnn_cnn64_9.dll',
    'cudnn_adv64_9.dll',
    'cudnn_heuristic64_9.dll',
    'cublas64_12.dll',
    'cudart64_12.dll',
]

extra_binaries = []
all_nvidia_dlls = glob.glob(os.path.join(site_packages, 'nvidia', '**', 'bin', '*.dll'), recursive=True)
all_onnx_dlls = glob.glob(os.path.join(site_packages, 'onnxruntime', 'capi', '*.dll'))
all_dlls = all_nvidia_dlls + all_onnx_dlls

for dll in all_dlls:
    if os.path.basename(dll) in required_dlls:
        extra_binaries.append((dll, '.'))

block_cipher = None

hidden_imports = [
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'pydantic_settings',
    'insightface',
    'passlib.handlers.bcrypt',
    'jobs.cleanup_actors',
    'jobs.cleanup_empty_actor_dirs',
    'jobs.cleanup_images',
    'jobs.repair_empty_actor_photos',
    'jobs.scrape_stashdb',
    'jobs.build_index',
    'insightface.app',
    'insightface.model_zoo',
    'faiss',
    'cv2',
    'PIL',
    'numpy',
    'sqlite3',
    'fastapi'
]

gui_backend_excludes = [
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    '_tkinter',
    'tkinter',
    'tcl',
    'tk',
    'matplotlib.backends.backend_qt',
    'matplotlib.backends.backend_qtagg',
    'matplotlib.backends.backend_qtcairo',
    'matplotlib.backends.backend_qt5',
    'matplotlib.backends.backend_qt5agg',
    'matplotlib.backends.backend_qt5cairo',
    'matplotlib.backends.backend_tkagg',
    'matplotlib.backends.backend_tkcairo',
    'matplotlib.backends.qt_compat',
]

a = Analysis(
    ['backend_main.py'],
    pathex=['.'],
    binaries=extra_binaries,
    datas=[],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={'matplotlib': {'backends': 'Agg'}},
    runtime_hooks=[],
    excludes=gui_backend_excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

package_collected_dlls = {
    'nvidia\\cublas\\bin\\cublaslt64_12.dll',
    'nvidia\\cudnn\\bin\\cudnn_graph64_9.dll',
    'nvidia\\cudnn\\bin\\cudnn_ops64_9.dll',
    'onnxruntime\\capi\\onnxruntime_providers_cuda.dll',
    'onnxruntime\\capi\\onnxruntime_providers_shared.dll',
}
collected_targets = {
    target.replace('/', '\\').lower()
    for target, _, _ in a.binaries
}
root_duplicate_dlls = {
    target.rsplit('\\', 1)[-1]
    for target in package_collected_dlls
    if target in collected_targets
}
a.binaries = [
    binary
    for binary in a.binaries
    if binary[0].replace('/', '\\').lower() not in root_duplicate_dlls
]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FaceBackend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False, # CONSOLE DISABLED
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FaceBackend',
)
