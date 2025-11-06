# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.building.api import PYZ, EXE, COLLECT
from PyInstaller.building.build_main import Analysis
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# --- Сбор скрытых импортов ---
hidden_imports = []
for pkg in ['pandas', 'numpy', 'openpyxl', 'lxml', 'ttkbootstrap', 'tkinter', 'pyobjc', 'objc', 'AppKit']:
    hidden_imports += collect_submodules(pkg)

# --- Сбор данных ---
datas = collect_data_files('ttkbootstrap')
datas += collect_data_files('pandas')
datas += collect_data_files('openpyxl')
datas += collect_data_files('xlrd')
datas += collect_data_files('xlwings')
datas += collect_data_files('lxml')

if os.path.exists('assets/icon.icns'):
    app_icon = 'assets/icon.icns'
    datas += [('assets/icon.icns', 'assets')]
elif os.path.exists('assets/icon.ico'):
    app_icon = 'assets/icon.ico'
    datas += [('assets/icon.ico', 'assets')]
else:
    app_icon = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='Pricelist',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=app_icon,
)

# --- Создание полноценного macOS .app ---
app = BUNDLE(
    exe,
    name='Pricelist.app',
    icon=app_icon,
    bundle_identifier='com.yourcompany.pricelist',
    info_plist={
        'CFBundleDisplayName': 'Pricelist',
        'CFBundleName': 'Pricelist',
        'CFBundleVersion': '1.0',
        'CFBundleShortVersionString': '1.0',
        'CFBundleExecutable': 'Pricelist',
        'CFBundlePackageType': 'APPL',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '10.13',
    },
)