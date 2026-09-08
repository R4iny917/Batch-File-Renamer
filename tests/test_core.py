import tempfile
import unittest
from pathlib import Path

from renamer.core import Rules, build_preview


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def file(self, name):
        path = self.root / name
        path.write_bytes(b"original")
        return path

    def test_rule_order_chinese_extension_and_number(self):
        source = self.file("照片.JPG")
        row = build_preview([source], Rules(prefix="旅行_", suffix="_精选", numbering=True))[0]
        self.assertEqual(row.target.name, "旅行_照片_精选_001.JPG")
        self.assertFalse(row.error)
        self.assertEqual(source.read_bytes(), b"original")

    def test_only_last_extension_is_preserved(self):
        row = build_preview([self.file("archive.tar.gz")], Rules(find="tar", replace="zip"))[0]
        self.assertEqual(row.target.name, "archive.zip.gz")

    def test_numbering_follows_input_and_does_not_truncate(self):
        paths = [self.file("b"), self.file("a")]
        rows = build_preview(paths, Rules(numbering=True, start=99, digits=1))
        self.assertEqual([r.target.name for r in rows], ["b_99", "a_100"])

    def test_empty_find_does_not_insert_replacement(self):
        row = build_preview([self.file("a.txt")], Rules(replace="X"))[0]
        self.assertEqual(row.target.name, "a.txt")
        self.assertFalse(row.changed)

    def test_replacement_is_case_sensitive(self):
        row = build_preview([self.file("Aa.txt")], Rules(find="a", replace="b"))[0]
        self.assertEqual(row.target.name, "Ab.txt")

    def test_empty_stem_is_rejected(self):
        row = build_preview([self.file("a.txt")], Rules(find="a"))[0]
        self.assertTrue(row.error)

    def test_invalid_windows_names(self):
        source = self.file("a")
        for name in ["CON", "con.txt", "COM1.log", "LPT².txt", "bad:", "bad/part", "bad\\part", "a?", "a\x01", "a.", "a ", "a" * 256]:
            with self.subTest(name=name):
                self.assertTrue(build_preview([source], Rules(find="a", replace=name))[0].error)

    def test_case_only_change_is_rejected(self):
        row = build_preview([self.file("a.txt")], Rules(find="a", replace="A"))[0]
        self.assertTrue(row.error)

    def test_duplicate_target_rejects_both_rows(self):
        paths = [self.file("a.txt"), self.file("aa.txt")]
        rows = build_preview(paths, Rules(find="a", replace="", prefix="x"))
        self.assertTrue(all(r.error for r in rows))

    def test_occupied_target_is_rejected_even_when_selected(self):
        paths = [self.file("a.txt"), self.file("xa.txt")]
        rows = build_preview(paths, Rules(prefix="x"))
        self.assertTrue(rows[0].error)
        self.assertEqual(paths[1].read_bytes(), b"original")

    def test_missing_file_and_directory_rejected(self):
        rows = build_preview([self.root / "missing", self.root], Rules(prefix="x"))
        self.assertTrue(all(r.error for r in rows))

    def test_same_name_in_different_folders_is_allowed(self):
        folder = self.root / "sub"
        folder.mkdir()
        other = folder / "a.txt"
        other.write_bytes(b"other")
        rows = build_preview([self.file("a.txt"), other], Rules(prefix="x"))
        self.assertTrue(all(not r.error for r in rows))

    def test_invalid_number_settings_are_rejected(self):
        source = self.file("a")
        for rules in [Rules(numbering=True, start=-1), Rules(numbering=True, digits=0)]:
            self.assertTrue(build_preview([source], rules)[0].error)


if __name__ == "__main__":
    unittest.main()
