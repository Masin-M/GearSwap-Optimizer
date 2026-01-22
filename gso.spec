# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for FFXI Gear Set Optimizer
Build with: pyinstaller gso.spec
"""

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

# =============================================================================
# Collect PIL/Pillow properly
# =============================================================================
pil_datas, pil_binaries, pil_hiddenimports = collect_all('PIL')

# =============================================================================
# Hidden imports for FastAPI/Uvicorn/Pydantic ecosystem
# =============================================================================
hidden_imports = [
    # FastAPI and dependencies
    'fastapi',
    'starlette',
    'starlette.applications',
    'starlette.middleware',
    'starlette.middleware.cors',
    'starlette.routing',
    'starlette.responses',
    'starlette.staticfiles',
    'starlette.templating',
    
    # Uvicorn
    'uvicorn',
    'uvicorn.config',
    'uvicorn.main',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    
    # Pydantic
    'pydantic',
    'pydantic.fields',
    'pydantic_core',
    'pydantic_settings',
    
    # Async support
    'anyio',
    'anyio._backends',
    'anyio._backends._asyncio',
    
    # HTTP/Network
    'httptools',
    'websockets',
    'h11',
    
    # System tray
    'pystray',
    'pystray._win32',
    
    # Multiprocessing (for numba if used)
    'multiprocessing',
    
    # Email (sometimes needed by FastAPI)
    'email.mime',
    'email.mime.text',
    'email.mime.multipart',
    
    # Standard library modules sometimes missed
    'json',
    'csv',
    'pickle',
    'dataclasses',
    'typing',
    'enum',
    'pathlib',
]

# Add PIL hidden imports
hidden_imports.extend(pil_hiddenimports)

# Try to collect numba if available (optional)
try:
    numba_datas, numba_binaries, numba_hiddenimports = collect_all('numba')
    hidden_imports.extend(numba_hiddenimports)
except:
    numba_datas = []
    numba_binaries = []

# =============================================================================
# Data files to include
# =============================================================================
datas = [
    # Static web files
    ('static', 'static'),
    
    # wsdist module
    ('wsdist_beta-main', 'wsdist_beta-main'),
    
    # Data files
    ('augment_data', 'augment_data'),
    
    # Lua files
    ('augments.lua', '.'),
    ('items.lua', '.'),
    ('item_descriptions.lua', '.'),
    
    # Icons
    ('icon.ico', '.'),
    ('tray_icon.png', '.'),
]

# Add PIL data files
datas.extend(pil_datas)

# Add numba data files if available
if numba_datas:
    datas.extend(numba_datas)

# =============================================================================
# Binaries
# =============================================================================
binaries = []
binaries.extend(pil_binaries)
if numba_binaries:
    binaries.extend(numba_binaries)

# =============================================================================
# Excludes - modules we don't need
# =============================================================================
excludes = [
    'tkinter',
    'matplotlib',
    'scipy',
    'pandas',
    'IPython',
    'jupyter',
    'notebook',
    'pytest',
    'sphinx',
    # Do NOT exclude PIL!
]

# =============================================================================
# Analysis
# =============================================================================
a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

# =============================================================================
# PYZ Archive
# =============================================================================
pyz = PYZ(a.pure)

# =============================================================================
# Executable
# =============================================================================
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FFXI_Gear_Optimizer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
)

# =============================================================================
# Collect all files
# =============================================================================
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FFXI_Gear_Optimizer',
)
