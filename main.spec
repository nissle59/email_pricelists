# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],  # можешь указать абсолютный путь к проекту, если нужно
    binaries=[],
    datas=[
        ('assets/icon.ico', 'assets'),  # если хочешь включить иконку внутрь exe
    ],
    hiddenimports=['pandas', 'numpy', 'openpyxl', 'lxml', 'ttkbootstrap'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

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
    console=False,                    # --noconsole
    icon='assets/icon.ico',           # --icon=assets/icon.ico
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Pricelist',                 # имя итогового каталога (можно любое)
)