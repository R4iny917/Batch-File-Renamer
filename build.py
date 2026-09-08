import os
import shutil
import struct
import subprocess
import sys
import sysconfig
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NAME = "Batch File Renamer"


def make_icon():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QBuffer, QIODevice
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    icon = QIcon(str(ROOT / "renamer/assets/app.svg"))
    images = []
    for size in (16, 24, 32, 48, 64, 128, 256):
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not icon.pixmap(size, size).save(buffer, "PNG"):
            raise RuntimeError("Cannot render application icon")
        images.append((size, bytes(buffer.data())))
    offset = 6 + 16 * len(images)
    result = bytearray(struct.pack("<HHH", 0, 1, len(images)))
    for size, data in images:
        result.extend(struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset))
        offset += len(data)
    for _, data in images:
        result.extend(data)
    (ROOT / "build").mkdir(exist_ok=True)
    (ROOT / "build/app.ico").write_bytes(result)


def main():
    if sys.platform != "win32" or sysconfig.get_platform() != "win-amd64":
        raise SystemExit("Build this package with x64 Python on Windows x64.")
    make_icon()
    build_env = os.environ.copy()
    windows = Path(os.environ["SystemRoot"])
    build_env["PATH"] = os.pathsep.join(map(str, (Path(sys.executable).parent, Path(sys.base_prefix), windows / "System32", windows)))
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", str(ROOT / f"{NAME}.spec")],
        cwd=ROOT, check=True, env=build_env,
    )
    bundle = ROOT / "dist" / NAME
    shutil.copy2(ROOT / "README.md", bundle / "README.md")
    archive = shutil.make_archive(str(ROOT / "dist" / f"{NAME}-Windows-x64"), "zip", ROOT / "dist", NAME)
    print(f"Portable package: {archive}")


if __name__ == "__main__":
    main()
