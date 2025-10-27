# -*- mode: python ; coding: utf-8 -*-
block_cipher = None

def get_pandas_path():
    import pandas
    pandas_path = pandas.__path__[0]
    return pandas_path

import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# --- Сбор всех скрытых импортов ---
hidden_imports = []
for pkg in ['pandas', 'numpy', 'openpyxl', 'lxml', 'ttkbootstrap']:
    hidden_imports += collect_submodules(pkg)

# --- Сбор данных (иконки, шаблоны и т.п.) ---
datas = collect_data_files('ttkbootstrap')
datas += collect_data_files('pandas')
datas += collect_data_files('openpyxl')
datas += collect_data_files('lxml')
datas += [('assets/icon.ico', 'assets')]  # иконка

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

dict_tree = Tree(get_pandas_path(), prefix='pandas', excludes=["*.pyc"])
a.datas += dict_tree
a.binaries = filter(lambda x: 'pandas' not in x[0], a.binaries)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Pricelist',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='assets/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name='Pricelist',
)