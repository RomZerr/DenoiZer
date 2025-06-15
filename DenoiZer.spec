# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['DenoiZer.py'],
    pathex=[],
    binaries=[],
    datas=[('DenoiZer_icon.png', '.'), ('DenoiZer_icon.ico', '.'), ('ExrMerge.py', '.'), ('Integrator_Denoizer.py', '.'), ('fonts\\\\CutePixel.ttf', 'fonts'), ('fonts\\\\Minecrafter.Alt.ttf', 'fonts')],
    hiddenimports=['numpy', 'numpy.core', 'numpy.core._methods', 'numpy.lib.format'],
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
    [],
    exclude_binaries=True,
    name='DenoiZer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['DenoiZer_icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DenoiZer',
)
