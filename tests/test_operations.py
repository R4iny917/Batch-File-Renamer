import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from renamer.core import Rules, build_preview
from renamer.operations import RenameSession
import renamer.operations as operations


class OperationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.a, self.b = self.root / "a.txt", self.root / "b.txt"
        self.a.write_bytes(b"first")
        self.b.write_bytes(b"second")
        self.session = RenameSession()
        self.rows = build_preview([self.a, self.b], Rules(prefix="x"))
        self.real_rename = operations.rename_locked

    def test_execute_and_undo_preserve_contents(self):
        result = self.session.execute(self.rows)
        self.assertTrue(result.ok, result.errors)
        self.assertFalse(self.a.exists())
        self.assertEqual((self.root / "xa.txt").read_bytes(), b"first")
        self.assertEqual((self.root / "xb.txt").read_bytes(), b"second")
        self.assertTrue(self.session.undo().ok)
        self.assertEqual(self.a.read_bytes(), b"first")
        self.assertEqual(self.b.read_bytes(), b"second")
        self.assertFalse(self.session.history)

    def test_stale_preview_does_not_rename_any_file(self):
        self.b.write_bytes(b"modified elsewhere")
        result = self.session.execute(self.rows)
        self.assertFalse(result.ok)
        self.assertFalse(result.moves, result.errors)
        self.assertEqual(self.a.read_bytes(), b"first")
        self.assertFalse((self.root / "xa.txt").exists())

    def test_replaced_source_is_rejected(self):
        replacement = self.root / "replacement"
        replacement.write_bytes(b"first")
        os.replace(replacement, self.a)
        self.assertFalse(self.session.execute(self.rows).ok)
        self.assertTrue(self.b.exists())

    def test_preexisting_target_does_not_overwrite(self):
        target = self.root / "xa.txt"
        target.write_bytes(b"unrelated")
        self.assertFalse(self.session.execute(self.rows).ok)
        self.assertEqual(target.read_bytes(), b"unrelated")
        self.assertTrue(self.a.exists())

    def test_target_created_after_preflight_is_not_overwritten(self):
        def race(source, target, snapshot):
            target.write_bytes(b"raced")
            self.real_rename(source, target, snapshot)
        with patch("renamer.operations.rename_locked", side_effect=race):
            self.assertFalse(self.session.execute(self.rows).ok)
        self.assertEqual((self.root / "xa.txt").read_bytes(), b"raced")
        self.assertEqual(self.a.read_bytes(), b"first")

    def test_second_failure_rolls_back_first(self):
        def fail_second(source, target, snapshot):
            if source == self.b:
                raise PermissionError("模拟文件被锁定")
            self.real_rename(source, target, snapshot)
        with patch("renamer.operations.rename_locked", side_effect=fail_second):
            result = self.session.execute(self.rows)
        self.assertFalse(result.ok)
        self.assertEqual(self.a.read_bytes(), b"first")
        self.assertEqual(self.b.read_bytes(), b"second")
        self.assertFalse(self.session.pending)
        self.assertFalse(result.moves)

    def test_failed_rollback_is_kept_and_can_be_recovered(self):
        def fail_and_occupy(source, target, snapshot):
            if source == self.b:
                self.a.write_bytes(b"intruder")
                raise PermissionError("模拟第二个文件失败")
            self.real_rename(source, target, snapshot)
        with patch("renamer.operations.rename_locked", side_effect=fail_and_occupy):
            result = self.session.execute(self.rows)
        self.assertFalse(result.ok)
        self.assertEqual(len(result.moves), 1)
        self.assertEqual(len(self.session.pending), 1)
        self.assertEqual(self.a.read_bytes(), b"intruder")
        self.assertEqual((self.root / "xa.txt").read_bytes(), b"first")
        self.assertFalse(self.session.execute(build_preview([self.b], Rules(prefix="z"))).ok)
        self.a.unlink()
        self.assertTrue(self.session.recover().ok)
        self.assertEqual(self.a.read_bytes(), b"first")
        self.assertFalse(self.session.pending)

    def test_undo_preflight_is_all_or_nothing(self):
        self.assertTrue(self.session.execute(self.rows).ok)
        self.a.write_bytes(b"intruder")
        self.assertFalse(self.session.undo().ok)
        self.assertTrue((self.root / "xb.txt").exists())
        self.assertEqual(self.a.read_bytes(), b"intruder")
        self.assertTrue(self.session.history)

    def test_undo_rejects_file_changed_after_rename(self):
        self.assertTrue(self.session.execute(self.rows).ok)
        (self.root / "xa.txt").write_bytes(b"new content")
        self.assertFalse(self.session.undo().ok)
        self.assertFalse(self.a.exists())
        self.assertTrue((self.root / "xb.txt").exists())

    def test_mid_undo_failure_restores_renamed_state(self):
        self.assertTrue(self.session.execute(self.rows).ok)
        def fail_a(source, target, snapshot):
            if source.name == "xa.txt":
                raise PermissionError("模拟撤销失败")
            self.real_rename(source, target, snapshot)
        with patch("renamer.operations.rename_locked", side_effect=fail_a):
            result = self.session.undo()
        self.assertFalse(result.ok)
        self.assertFalse(result.moves, result.errors)
        self.assertEqual((self.root / "xb.txt").read_bytes(), b"second")
        self.assertFalse(self.b.exists())
        self.assertTrue(self.session.history)
        self.assertTrue(self.session.undo().ok)

    def test_noop_and_failed_batch_preserve_previous_history(self):
        self.assertTrue(self.session.execute(self.rows).ok)
        history = list(self.session.history)
        self.assertTrue(self.session.execute([]).ok)
        self.assertEqual(self.session.history, history)
        invalid = build_preview([self.root / "missing"], Rules(prefix="z"))
        self.assertFalse(self.session.execute(invalid).ok)
        self.assertEqual(self.session.history, history)

    def test_successful_new_batch_replaces_history(self):
        self.assertTrue(self.session.execute(self.rows).ok)
        next_rows = build_preview([self.root / "xa.txt"], Rules(prefix="y"))
        self.assertTrue(self.session.execute(next_rows).ok)
        self.assertTrue(self.session.undo().ok)
        self.assertTrue((self.root / "xa.txt").exists())
        self.assertFalse(self.a.exists())

    def test_source_replaced_between_check_and_rename_is_not_renamed(self):
        real_check = operations.check_move
        calls = 0
        def check_then_replace(move):
            nonlocal calls
            real_check(move)
            calls += 1
            if calls == 3:
                replacement = self.root / "replacement"
                replacement.write_bytes(b"replacement")
                os.replace(replacement, self.a)
        with patch("renamer.operations.check_move", side_effect=check_then_replace):
            result = self.session.execute(self.rows)
        self.assertFalse(result.ok)
        self.assertEqual(self.a.read_bytes(), b"replacement")
        self.assertFalse((self.root / "xa.txt").exists())
        self.assertTrue(self.b.exists())

    def test_locked_source_cannot_be_replaced_during_native_rename(self):
        from renamer import windows
        native = windows.set_file_information
        attempts = []
        def try_replace(handle, info_class, buffer, size):
            replacement = self.root / "replacement"
            replacement.write_bytes(b"replacement")
            try:
                os.replace(replacement, self.a)
                attempts.append("replaced")
            except PermissionError:
                attempts.append("blocked")
            return native(handle, info_class, buffer, size)
        with patch("renamer.windows.set_file_information", side_effect=try_replace):
            result = self.session.execute(self.rows[:1])
        self.assertTrue(result.ok, result.errors)
        self.assertEqual(attempts, ["blocked"])
        self.assertEqual((self.root / "xa.txt").read_bytes(), b"first")
        self.assertTrue(self.session.undo().ok)

    def test_failed_undo_rollback_can_recover_and_retry_undo(self):
        self.assertTrue(self.session.execute(self.rows).ok)
        occupied = self.root / "xb.txt"
        def fail_a(source, target, snapshot):
            if source.name == "xa.txt":
                occupied.write_bytes(b"intruder")
                raise PermissionError("模拟撤销失败")
            self.real_rename(source, target, snapshot)
        with patch("renamer.operations.rename_locked", side_effect=fail_a):
            result = self.session.undo()
        self.assertFalse(result.ok)
        self.assertTrue(self.session.pending)
        self.assertEqual(self.b.read_bytes(), b"second")
        self.assertEqual(occupied.read_bytes(), b"intruder")
        occupied.unlink()
        self.assertTrue(self.session.recover().ok)
        self.assertTrue(self.session.history)
        self.assertTrue(self.session.undo().ok)
        self.assertEqual(self.a.read_bytes(), b"first")
        self.assertEqual(self.b.read_bytes(), b"second")


if __name__ == "__main__":
    unittest.main()
