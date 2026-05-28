# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []

# Collect customtkinter data, binaries, and hidden imports
tmp_ret = collect_all('customtkinter')
datas.extend(tmp_ret[0])
binaries.extend(tmp_ret[1])
hiddenimports.extend(tmp_ret[2])

# Explicitly declare local modules as hidden imports to ensure PyInstaller bundles them
hiddenimports.extend([
    'gui',
    'engine',
    'client',
    'parser',
    'models',
    'runtime.config',
    'runtime.logger',
    'runtime.utils',
    'runtime.checkpoint_store',
    'runtime.excel_processor',
])

# Bundle seed session_caches directory if it exists
if os.path.exists('session_caches'):
    datas.append(('session_caches', 'session_caches'))

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'unittest',
        'pydoc',
        'setuptools',
        'distutils',
        'numpy',
        'pandas',
        'matplotlib',
        'scipy',
        'tkinter.test',
        'pdb',
        'IPython',
        'docutils',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='AKTU_Result',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

app = BUNDLE(
    exe,
    name='AKTU_Result.app',
    icon=None,
    bundle_identifier='com.aktu.result',
)
