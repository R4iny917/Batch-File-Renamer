import os
import shutil
import stat
import struct
import subprocess
import sys
import sysconfig
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NAME = "Batch File Renamer"


def validate_native_ui():
    for scale in ("1", "1.25", "1.5", "2"):
        environment = os.environ.copy()
        environment["QT_SCREEN_SCALE_FACTORS"] = scale
        environment["QT_SCALE_FACTOR"] = "1"
        print(f"Checking native UI at {float(scale):.0%} scale", flush=True)
        subprocess.run(
            [sys.executable, str(ROOT / "tests/test_native_ui.py"), "--run"],
            cwd=ROOT, check=True, env=environment,
        )


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


def publish_package(candidate, archive, dist):
    if not candidate.is_dir() or not archive.is_file():
        raise FileNotFoundError("The new package or archive is missing; existing versions were not changed.")
    dist.mkdir(exist_ok=True)
    latest, previous = dist / "latest", dist / "previous"
    retired = candidate.parent / "retired"
    for path in (dist, latest, previous, candidate):
        attributes = getattr(path.lstat(), "st_file_attributes", 0) if path.exists() else 0
        if path.is_symlink() or attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise RuntimeError(f"Refusing to rotate a linked directory: {path}")
    moved = []
    created = []
    try:
        for source, target in ((previous, retired), (latest, previous), (candidate, latest)):
            if source.exists():
                if not target.exists():
                    target.mkdir()
                    created.append(target)
                for item in list(source.iterdir()):
                    destination = target / item.name
                    item.rename(destination)
                    moved.append((item, destination))
        archive.replace(dist / f"{NAME}-Windows-x64.zip")
    except OSError:
        for source, target in reversed(moved):
            target.rename(source)
        for directory in reversed(created):
            directory.rmdir()
        raise


def main():
    if sys.platform != "win32" or sysconfig.get_platform() != "win-amd64":
        raise SystemExit("Build this package with x64 Python on Windows x64.")
    validate_native_ui()
    make_icon()
    build_env = os.environ.copy()
    windows = Path(os.environ["SystemRoot"])
    build_env["PATH"] = os.pathsep.join(map(str, (Path(sys.executable).parent, Path(sys.base_prefix), windows / "System32", windows)))
    with tempfile.TemporaryDirectory(prefix="package-", dir=ROOT / "build") as temporary:
        stage = Path(temporary)
        candidate = stage / "output"
        subprocess.run(
            [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm",
             "--distpath", str(candidate), str(ROOT / f"{NAME}.spec")],
            cwd=ROOT, check=True, env=build_env,
        )
        bundle = candidate / NAME
        if not (bundle / f"{NAME}.exe").is_file():
            raise RuntimeError("Build did not produce the expected executable.")
        shutil.copy2(ROOT / "README.md", bundle / "README.md")
        archive = Path(shutil.make_archive(str(stage / "package"), "zip", candidate, NAME))
        publish_package(candidate, archive, ROOT / "dist")
    print(f"Latest application: {ROOT / 'dist' / 'latest' / NAME / (NAME + '.exe')}")
    print(f"Portable package: {ROOT / 'dist' / (NAME + '-Windows-x64.zip')}")


if __name__ == "__main__":
    main()
