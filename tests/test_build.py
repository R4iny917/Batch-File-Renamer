import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import build


class PackageRotationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.dist = self.root / "dist"
        self.dist.mkdir()
        self.stage = self.root / "stage"
        self.stage.mkdir()
        self.candidate = self.stage / "output"
        self.candidate.mkdir()
        (self.candidate / "version.txt").write_text("new")
        self.archive = self.stage / "package.zip"
        self.archive.write_bytes(b"new archive")

    def seed(self):
        for name, version in (("latest", "current"), ("previous", "old")):
            folder = self.dist / name
            folder.mkdir()
            (folder / "version.txt").write_text(version)
        (self.dist / f"{build.NAME}-Windows-x64.zip").write_bytes(b"current archive")

    def test_first_package_has_only_latest(self):
        build.publish_package(self.candidate, self.archive, self.dist)
        self.assertEqual((self.dist / "latest/version.txt").read_text(), "new")
        self.assertFalse((self.dist / "previous").exists())

    def test_success_keeps_latest_and_previous(self):
        self.seed()
        build.publish_package(self.candidate, self.archive, self.dist)
        self.assertEqual((self.dist / "latest/version.txt").read_text(), "new")
        self.assertEqual((self.dist / "previous/version.txt").read_text(), "current")
        self.assertEqual(sorted(p.name for p in self.dist.iterdir() if p.is_dir()), ["latest", "previous"])
        self.assertEqual((self.dist / f"{build.NAME}-Windows-x64.zip").read_bytes(), b"new archive")

    def test_locked_latest_restores_both_packages(self):
        self.seed()
        rename = Path.rename

        def locked(path, target):
            if path.parent == self.dist / "latest":
                raise PermissionError("Package in use")
            return rename(path, target)

        with patch.object(Path, "rename", locked), self.assertRaises(PermissionError):
            build.publish_package(self.candidate, self.archive, self.dist)
        self.assert_original_packages()

    def test_archive_failure_restores_both_packages(self):
        self.seed()
        with patch.object(Path, "replace", side_effect=PermissionError("Archive in use")), self.assertRaises(PermissionError):
            build.publish_package(self.candidate, self.archive, self.dist)
        self.assert_original_packages()

    def test_missing_archive_leaves_existing_packages_untouched(self):
        self.seed()
        self.archive.unlink()
        with self.assertRaises(FileNotFoundError):
            build.publish_package(self.candidate, self.archive, self.dist)
        self.assert_original_packages()

    def test_fixed_version_directories_are_never_renamed(self):
        self.seed()
        rename = Path.rename

        def locked_directory(path, target):
            if path in (self.dist / "latest", self.dist / "previous"):
                raise PermissionError("Version directory is open")
            return rename(path, target)

        with patch.object(Path, "rename", locked_directory):
            build.publish_package(self.candidate, self.archive, self.dist)
        self.assertEqual((self.dist / "latest/version.txt").read_text(), "new")
        self.assertEqual((self.dist / "previous/version.txt").read_text(), "current")

    def assert_original_packages(self):
        self.assertEqual((self.dist / "latest/version.txt").read_text(), "current")
        self.assertEqual((self.dist / "previous/version.txt").read_text(), "old")
        self.assertEqual((self.dist / f"{build.NAME}-Windows-x64.zip").read_bytes(), b"current archive")
