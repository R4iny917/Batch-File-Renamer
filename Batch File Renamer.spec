from pathlib import Path

root = Path(SPECPATH)
a = Analysis(
    [str(root / 'renamer' / '__main__.py')],
    pathex=[str(root)],
    datas=[(str(root / 'renamer' / 'assets' / 'app.svg'), 'renamer/assets')],
    excludes=['PySide6.QtQml', 'PySide6.QtQuick'],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='Batch File Renamer',
    console=False,
    icon=str(root / 'build' / 'app.ico'),
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name='Batch File Renamer', upx=False)
