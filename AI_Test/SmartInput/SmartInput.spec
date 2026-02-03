# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.hooks import get_module_file_attribute

# 获取 Pinyin2Hanzi 数据路径
try:
    pinyin2hanzi_data = os.path.join(os.path.dirname(get_module_file_attribute('Pinyin2Hanzi')), 'data')
except:
    # 备用方案：使用常见的虚拟环境路径
    pinyin2hanzi_data = os.path.join(sys.prefix, 'lib', 'site-packages', 'Pinyin2Hanzi', 'data')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[(pinyin2hanzi_data, 'Pinyin2Hanzi/data'), ('zh.png', '.'), ('en.png', '.')],
    hiddenimports=['PIL', 'PIL._imagingtk', 'PIL._tkinter_finder', 'pystray'],
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
    a.binaries,
    a.datas,
    [],
    name='SmartInput',
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
