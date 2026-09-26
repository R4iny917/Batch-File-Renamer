import tempfile
import unittest
from pathlib import Path

from renamer.core import Rules, Snapshot
from renamer.operations import Move, Result
from renamer.workspace import Workspace


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.first = self.root / "first.txt"
        self.second = self.root / "second.txt"
        for path in (self.first, self.second):
            path.write_bytes(b"original")
        self.workspace = Workspace()

    def test_deduplicate_preserves_input_order_and_renumbers_after_remove(self):
        self.workspace.add_paths([self.second, str(self.first), self.second])
        self.workspace.set_rules(Rules(numbering=True, start=0, digits=2))
        self.assertEqual([r.target.name for r in self.workspace.rows], ["second_00.txt", "first_01.txt"])
        self.workspace.remove_rows({0})
        self.assertEqual(self.workspace.paths, [self.first])
        self.assertEqual(self.workspace.rows[0].target.name, "first_00.txt")

    def test_reordering_paths_updates_preview_and_numbering(self):
        self.workspace.add_paths([self.first, self.second])
        self.workspace.set_rules(Rules(numbering=True, start=1, digits=3))

        self.workspace.reorder_paths([self.second, self.first])

        self.assertEqual(self.workspace.paths, [self.second, self.first])
        self.assertEqual([row.target.name for row in self.workspace.rows], ["second_001.txt", "first_002.txt"])

    def test_reordering_paths_rejects_incomplete_or_duplicate_lists(self):
        self.workspace.add_paths([self.first, self.second])

        self.workspace.reorder_paths([self.second])
        self.workspace.reorder_paths([self.second, self.second])

        self.assertEqual(self.workspace.paths, [self.first, self.second])

    def test_refresh_detects_external_changes_without_changing_rules(self):
        rules = Rules(prefix="x")
        self.workspace.add_paths([self.first])
        self.workspace.set_rules(rules)
        (self.root / "xfirst.txt").write_bytes(b"occupied")
        self.workspace.refresh()
        self.assertTrue(self.workspace.rows[0].error)
        self.assertEqual(self.workspace.rules, rules)
        self.assertEqual(self.first.read_bytes(), b"original")

    def test_success_resets_rules_and_updates_only_visible_paths(self):
        self.workspace.add_paths([self.first, self.second])
        self.workspace.set_rules(Rules(prefix="x"))
        moves = [Move(row.source, row.target, row.snapshot) for row in self.workspace.rows]
        for move in moves:
            move.source.rename(move.target)
        self.workspace.session.history = moves
        self.workspace.remove_rows({1})
        result = Result(True, "完成", moves=moves)
        self.workspace.apply_result(result, "execute")
        self.assertEqual(self.workspace.paths, [moves[0].target])
        self.assertEqual(self.workspace.rules, Rules())
        self.assertFalse(self.workspace.rows[0].changed)
        self.workspace.set_paths([])
        self.assertEqual(self.workspace.session.history, moves)
        self.assertIs(self.workspace.last_result, result)

    def test_partial_failure_and_recovery_preserve_rules_and_map_actual_moves(self):
        self.workspace.add_paths([self.first, self.second])
        rules = Rules(prefix="x")
        self.workspace.set_rules(rules)
        moved = Move(self.first, self.root / "xfirst.txt", Snapshot.capture(self.first))
        moved.source.rename(moved.target)
        self.workspace.apply_result(Result(False, "部分失败", ["占用"], [moved]), "execute")
        self.assertEqual(self.workspace.paths, [moved.target, self.second])
        self.assertEqual(self.workspace.rules, rules)
        moved.target.rename(moved.source)
        self.workspace.apply_result(Result(True, "恢复完成", moves=[moved.reverse()]), "recover")
        self.assertEqual(self.workspace.paths, [self.first, self.second])
        self.assertEqual(self.workspace.rules, rules)

    def test_no_op_execute_and_undo_keep_rules(self):
        rules = Rules(prefix="x")
        self.workspace.set_rules(rules)
        self.workspace.apply_result(Result(True, "无改动"), "execute")
        self.assertEqual(self.workspace.rules, rules)
        self.workspace.apply_result(Result(True, "撤销完成"), "undo")
        self.assertEqual(self.workspace.rules, rules)


if __name__ == "__main__":
    unittest.main()
