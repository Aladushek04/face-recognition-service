# -*- mode: python ; coding: utf-8 -*-

import os
import glob
import site

backend_runtime = os.environ.get('FACE_BACKEND_RUNTIME', 'gpu').strip().lower()
if backend_runtime not in {'cpu', 'gpu'}:
    raise ValueError(f"FACE_BACKEND_RUNTIME must be 'cpu' or 'gpu', got {backend_runtime!r}")

# Resolve DLLs
site_package_dirs = []
for candidate in site.getsitepackages() + [site.getusersitepackages()]:
    if candidate and os.path.isdir(candidate) and candidate not in site_package_dirs:
        site_package_dirs.append(candidate)

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
all_dlls = []
if backend_runtime == 'gpu':
    for site_packages in site_package_dirs:
        all_dlls.extend(glob.glob(os.path.join(site_packages, 'nvidia', '**', 'bin', '*.dll'), recursive=True))
        all_dlls.extend(glob.glob(os.path.join(site_packages, 'onnxruntime', 'capi', '*.dll')))

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

runtime_excludes = []
if backend_runtime == 'cpu':
    runtime_excludes = [
        'nvidia',
        'nvidia.cublas',
        'nvidia.cuda_runtime',
        'nvidia.cudnn',
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
    excludes=gui_backend_excludes + runtime_excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

if backend_runtime == 'gpu':
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
else:
    cuda_binary_markers = (
        'nvidia\\',
        'onnxruntime\\capi\\onnxruntime_providers_cuda.dll',
        'onnxruntime\\capi\\onnxruntime_providers_tensorrt.dll',
    )
    a.binaries = [
        binary
        for binary in a.binaries
        if not any(binary[0].replace('/', '\\').lower().startswith(marker) for marker in cuda_binary_markers)
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
