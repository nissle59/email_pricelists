# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.building.api import PYZ, EXE
from PyInstaller.building.build_main import Analysis
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# --- Сбор всех скрытых импортов ---
hidden_imports = []
for pkg in ['pandas', 'numpy', 'openpyxl', 'lxml', 'ttkbootstrap']:
    hidden_imports += collect_submodules(pkg)

# --- Сбор данных (иконки, шаблоны и т.п.) ---
datas = collect_data_files('ttkbootstrap')
datas += collect_data_files('pandas')
datas += collect_data_files('openpyxl')
datas += collect_data_files('xlrd')
datas += collect_data_files('xlwings')
datas += collect_data_files('lxml')

# Добавляем иконку и другие ресурсы
if os.path.exists('assets/icon.ico'):
    datas += [('assets/icon.ico', 'assets')]

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
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,  # бинарные файлы включаем прямо в EXE
    a.zipfiles,   # zip файлы включаем прямо в EXE
    a.datas,      # данные включаем прямо в EXE
    name='Pricelist',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    icon='assets/icon.ico' if os.path.exists('assets/icon.ico') else None,
    onefile=True  # ключевой параметр для одного файла
)