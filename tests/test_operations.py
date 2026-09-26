import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from renamer.core import Rules, build_preview
from renamer.operations import RenameSession
from renamer.recovery_store import RecoveryStore, RecoveryStoreError
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

    def test_successful_history_survives_session_restart_and_can_be_undone(self):
        store = RecoveryStore(self.root / "recovery.json")
        session = RenameSession(store)
        def rename(source, target, snapshot):
            os.rename(source, target)

        with patch("renamer.operations.rename_locked", side_effect=rename):
            self.assertTrue(session.execute(self.rows).ok)
            restarted = RenameSession(store)
            self.assertEqual(restarted.history, session.history)
            result = restarted.undo()

        self.assertTrue(result.ok, result.errors)
        self.assertTrue(self.a.exists())
        self.assertTrue(self.b.exists())
        self.assertIsNone(store.load())

    def test_interrupted_execute_after_move_can_be_recovered_after_restart(self):
        store = RecoveryStore(self.root / "recovery.json")
        session = RenameSession(store)

        def rename_then_crash(source, target, snapshot):
            os.rename(source, target)
            raise SystemExit("simulated process interruption")

        with patch("renamer.operations.rename_locked", side_effect=rename_then_crash):
            with self.assertRaises(SystemExit):
                session.execute(self.rows)

        restarted = RenameSession(store)
        self.assertTrue(restarted.pending)
        def rename(source, target, snapshot):
            os.rename(source, target)
        with patch("renamer.operations.rename_locked", side_effect=rename):
            result = restarted.recover()

        self.assertTrue(result.ok, result.errors)
        self.assertTrue(self.a.exists())
        self.assertFalse((self.root / "xa.txt").exists())
        self.assertIsNone(store.load())

    def test_interrupted_execute_before_move_clears_empty_transaction(self):
        store = RecoveryStore(self.root / "recovery.json")
        session = RenameSession(store)

        def crash_before_move(source, target, snapshot):
            raise SystemExit("simulated process interruption")

        with patch("renamer.operations.rename_locked", side_effect=crash_before_move):
            with self.assertRaises(SystemExit):
                session.execute(self.rows)

        restarted = RenameSession(store)

        self.assertFalse(restarted.pending)
        self.assertFalse(restarted.active)
        self.assertTrue(self.a.exists())
        self.assertIsNone(store.load())

    def test_interrupted_move_with_changed_target_is_not_recovered(self):
        store = RecoveryStore(self.root / "recovery.json")
        session = RenameSession(store)
        target = self.root / "xa.txt"

        def rename_then_crash(source, destination, snapshot):
            os.rename(source, destination)
            raise SystemExit("simulated process interruption")

        with patch("renamer.operations.rename_locked", side_effect=rename_then_crash):
            with self.assertRaises(SystemExit):
                session.execute(self.rows[:1])
        target.write_bytes(b"external replacement")

        restarted = RenameSession(store)
        result = restarted.recover()

        self.assertFalse(result.ok)
        self.assertTrue(target.exists())
        self.assertEqual(target.read_bytes(), b"external replacement")

    def test_startup_blocks_recovery_when_reverse_target_is_occupied(self):
        store = RecoveryStore(self.root / "recovery.json")
        snapshot = operations.Snapshot.capture(self.a)
        renamed = self.root / "renamed.txt"
        os.rename(self.a, renamed)
        self.a.write_bytes(b"external replacement")
        move = operations.Move(self.a, renamed, snapshot).reverse()
        store.save({
            "schema_version": 1,
            "history": [],
            "active": {
                "action": "recover",
                "moves": [RenameSession._move_to_state(move)],
                "completed": 0,
                "in_flight": None,
            },
        })

        restarted = RenameSession(store)

        self.assertTrue(restarted.recovery_error)
        self.assertFalse(restarted.execute(self.rows[:1]).ok)
        self.assertEqual(renamed.read_bytes(), b"first")
        self.assertEqual(self.a.read_bytes(), b"external replacement")
        self.assertIsNotNone(store.load())

    def test_interrupted_undo_resumes_after_restart(self):
        store = RecoveryStore(self.root / "recovery.json")
        session = RenameSession(store)

        def rename(source, target, snapshot):
            os.rename(source, target)

        with patch("renamer.operations.rename_locked", side_effect=rename):
            self.assertTrue(session.execute(self.rows).ok)

        def undo_then_crash(source, target, snapshot):
            os.rename(source, target)
            raise SystemExit("simulated process interruption")

        with patch("renamer.operations.rename_locked", side_effect=undo_then_crash):
            with self.assertRaises(SystemExit):
                session.undo()

        restarted = RenameSession(store)
        self.assertTrue(restarted.active)
        self.assertEqual(restarted.active["action"], "undo")
        self.assertEqual(restarted.recovery_action, "undo")
        with patch("renamer.operations.rename_locked", side_effect=rename):
            result = restarted.undo()

        self.assertTrue(result.ok, result.errors)
        self.assertTrue(self.a.exists())
        self.assertTrue(self.b.exists())
        self.assertIsNone(store.load())

    def test_recovery_finishes_when_move_completes_before_error_is_reported(self):
        store = RecoveryStore(self.root / "recovery.json")
        snapshot = operations.Snapshot.capture(self.a)
        target = self.root / "renamed.txt"
        os.rename(self.a, target)
        move = operations.Move(target, self.a, snapshot)
        store.save({
            "schema_version": 1,
            "history": [],
            "active": {
                "action": "recover",
                "moves": [RenameSession._move_to_state(move)],
                "completed": 0,
                "in_flight": None,
            },
        })
        session = RenameSession(store)

        def rename_then_report_error(source, destination, expected):
            os.rename(source, destination)
            raise PermissionError("simulated late filesystem error")

        with patch("renamer.operations.rename_locked", side_effect=rename_then_report_error):
            result = session.recover()

        self.assertTrue(result.ok, result.errors)
        self.assertTrue(self.a.exists())
        self.assertFalse(target.exists())
        self.assertFalse(session.has_recovery)
        self.assertIsNone(store.load())

    def test_interrupted_recovery_after_move_is_cleared_on_restart(self):
        store = RecoveryStore(self.root / "recovery.json")
        snapshot = operations.Snapshot.capture(self.a)
        renamed = self.root / "renamed.txt"
        os.rename(self.a, renamed)
        recovery_move = operations.Move(renamed, self.a, snapshot)
        store.save({
            "schema_version": 1,
            "history": [],
            "active": {
                "action": "recover",
                "moves": [RenameSession._move_to_state(recovery_move)],
                "completed": 0,
                "in_flight": None,
            },
        })
        session = RenameSession(store)

        def rename_then_crash(source, target, expected):
            os.rename(source, target)
            raise SystemExit("simulated process interruption")

        with patch("renamer.operations.rename_locked", side_effect=rename_then_crash):
            with self.assertRaises(SystemExit):
                session.recover()

        restarted = RenameSession(store)

        self.assertTrue(self.a.exists())
        self.assertFalse(renamed.exists())
        self.assertFalse(restarted.has_recovery)
        self.assertIsNone(store.load())

    def test_interrupted_after_last_rename_keeps_completed_batch_undoable(self):
        store = RecoveryStore(self.root / "recovery.json")
        session = RenameSession(store)

        def rename_then_crash(source, target, snapshot):
            os.rename(source, target)
            raise SystemExit("simulated process interruption")

        with patch("renamer.operations.rename_locked", side_effect=rename_then_crash):
            with self.assertRaises(SystemExit):
                session.execute(self.rows[:1])

        restarted = RenameSession(store)
        self.assertEqual(len(restarted.history), 1)
        def rename(source, target, snapshot):
            os.rename(source, target)
        with patch("renamer.operations.rename_locked", side_effect=rename):
            result = restarted.undo()

        self.assertTrue(result.ok, result.errors)
        self.assertTrue(self.a.exists())

    def test_persisted_history_rejects_changed_file_after_restart(self):
        store = RecoveryStore(self.root / "recovery.json")
        session = RenameSession(store)
        def rename(source, target, snapshot):
            os.rename(source, target)

        with patch("renamer.operations.rename_locked", side_effect=rename):
            self.assertTrue(session.execute(self.rows[:1]).ok)
        target = self.root / "xa.txt"
        target.write_bytes(b"external replacement")

        restarted = RenameSession(store)
        result = restarted.undo()

        self.assertFalse(result.ok)
        self.assertEqual(target.read_bytes(), b"external replacement")
        self.assertFalse(self.a.exists())

    def test_recovery_record_write_failure_prevents_first_move(self):
        store = RecoveryStore(self.root / "recovery.json")
        session = RenameSession(store)

        with patch.object(store, "save", side_effect=RecoveryStoreError("disk unavailable")):
            with self.assertRaises(RecoveryStoreError):
                session.execute(self.rows[:1])

        self.assertTrue(self.a.exists())
        self.assertFalse((self.root / "xa.txt").exists())
        self.assertTrue(session.recovery_error)
        self.assertFalse(session.execute(self.rows[:1]).ok)

    def test_checkpoint_write_failure_after_move_blocks_more_operations(self):
        store = RecoveryStore(self.root / "recovery.json")
        session = RenameSession(store)
        real_save = store.save
        calls = 0

        def fail_progress_write(state):
            nonlocal calls
            calls += 1
            if calls <= 2:
                real_save(state)
            else:
                raise RecoveryStoreError("disk unavailable")

        def rename(source, target, snapshot):
            os.rename(source, target)

        with patch.object(store, "save", side_effect=fail_progress_write):
            with patch("renamer.operations.rename_locked", side_effect=rename):
                with self.assertRaises(RecoveryStoreError):
                    session.execute(self.rows[:1])

        target = self.root / "xa.txt"
        self.assertTrue(target.exists())
        self.assertTrue(session.recovery_error)
        self.assertFalse(session.execute(self.rows[:1]).ok)

        restarted = RenameSession(store)
        self.assertEqual(len(restarted.history), 1)
        self.assertEqual(target.read_bytes(), b"first")

    def test_invalid_move_record_is_preserved_and_rejected(self):
        store = RecoveryStore(self.root / "recovery.json")
        invalid_state = {"schema_version": 1, "history": [{"source": "invalid"}], "active": None}
        store.save(invalid_state)

        with self.assertRaises(RecoveryStoreError):
            RenameSession(store)

        self.assertEqual(store.load(), invalid_state)

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

    def test_incomplete_rollback_survives_restart_and_preserves_previous_history(self):
        store = RecoveryStore(self.root / "recovery.json")
        session = RenameSession(store)

        def rename(source, target, snapshot):
            os.rename(source, target)

        with patch("renamer.operations.rename_locked", side_effect=rename):
            self.assertTrue(session.execute(self.rows).ok)
        previous_history = list(session.history)
        xa, xb = self.root / "xa.txt", self.root / "xb.txt"
        next_rows = build_preview([xa, xb], Rules(prefix="y"))

        def fail_second_and_occupy_rollback_target(source, target, snapshot):
            if source == xb:
                xa.write_bytes(b"external replacement")
                raise PermissionError("simulated second move failure")
            os.rename(source, target)

        with patch("renamer.operations.rename_locked", side_effect=fail_second_and_occupy_rollback_target):
            failed = session.execute(next_rows)

        self.assertFalse(failed.ok)
        self.assertTrue(session.pending)
        restarted = RenameSession(store)
        self.assertEqual(restarted.recovery_action, "recover")
        self.assertEqual(restarted.history, previous_history)

        xa.unlink()
        restarted = RenameSession(store)
        self.assertFalse(restarted.recovery_error)
        with patch("renamer.operations.rename_locked", side_effect=rename):
            self.assertTrue(restarted.recover().ok)
            self.assertTrue(restarted.undo().ok)

        self.assertEqual(self.a.read_bytes(), b"first")
        self.assertEqual(self.b.read_bytes(), b"second")

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
