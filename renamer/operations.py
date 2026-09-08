import os
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .core import Entry, Snapshot, path_key, validate_name

if os.name == "nt":
    from .windows import rename_locked


@dataclass(frozen=True)
class Move:
    source: Path
    target: Path
    snapshot: Snapshot

    def reverse(self):
        return Move(self.target, self.source, self.snapshot)


@dataclass
class Result:
    ok: bool
    message: str
    errors: list[str] = field(default_factory=list)
    moves: list[Move] = field(default_factory=list)


def check_move(move: Move):
    if move.source.parent != move.target.parent:
        raise ValueError("仅允许在原目录内改名")
    validate_name(move.target.name)
    if move.source.name.casefold() == move.target.name.casefold():
        raise ValueError("不支持同名或仅大小写变化")
    if Snapshot.capture(move.source) != move.snapshot:
        raise ValueError("文件已变化，请刷新预览；撤销时需先处理外部修改")
    if any(p.name.casefold() == move.target.name.casefold() for p in move.target.parent.iterdir()):
        raise FileExistsError(f"目标名称已被占用：{move.target}")


def move_file(move: Move):
    if os.name != "nt":
        raise OSError("此版本仅支持 Windows 的不覆盖改名操作")
    check_move(move)
    rename_locked(move.source, move.target, move.snapshot)


def describe_error(move: Move, exc: Exception):
    return f"{move.source} → {move.target}\n{exc}"


class RenameSession:
    def __init__(self):
        self.history: list[Move] = []
        self.pending: list[Move] = []

    def _run(self, moves: list[Move], label: str) -> Result:
        errors = []
        targets = Counter(path_key(move.target) for move in moves)
        sources = Counter(path_key(move.source) for move in moves)
        for move in moves:
            try:
                if targets[path_key(move.target)] > 1 or sources[path_key(move.source)] > 1:
                    raise ValueError("本批次存在重复源文件或目标")
                check_move(move)
            except (OSError, ValueError) as exc:
                errors.append(describe_error(move, exc))
        if errors:
            return Result(False, f"{label}前检查未通过，未改动文件", errors)
        completed = []
        for move in moves:
            try:
                move_file(move)
                completed.append(move)
            except (OSError, ValueError) as exc:
                errors.append(describe_error(move, exc))
                remaining = []
                for done in reversed(completed):
                    try:
                        move_file(done.reverse())
                    except (OSError, ValueError) as rollback_exc:
                        remaining.append(done)
                        errors.append("恢复失败：" + describe_error(done.reverse(), rollback_exc))
                self.pending = list(reversed(remaining))
                message = (f"{label}未完成，仍有 {len(remaining)} 个文件需要恢复"
                           if remaining else f"{label}未完成，已恢复本批次的改动")
                return Result(False, message, errors, list(self.pending))
        return Result(True, f"已{label} {len(completed)} 个文件", moves=completed)

    def execute(self, entries: list[Entry]) -> Result:
        if self.pending:
            return Result(False, "请先完成失败批次的恢复")
        invalid = [f"{row.source}\n{row.error}" for row in entries if row.error]
        if invalid:
            return Result(False, "预览中存在错误，未改动文件", invalid)
        moves = []
        for row in entries:
            if row.changed:
                if row.snapshot is None:
                    return Result(False, "缺少文件快照，请刷新预览")
                moves.append(Move(row.source, row.target, row.snapshot))
        if not moves:
            return Result(True, "没有需要改名的文件")
        result = self._run(moves, "改名")
        if result.ok:
            self.history = list(result.moves)
        return result

    def undo(self) -> Result:
        if self.pending:
            return Result(False, "请先完成失败批次的恢复")
        if not self.history:
            return Result(False, "本次打开期间没有可撤销的改名")
        result = self._run([move.reverse() for move in reversed(self.history)], "撤销")
        if result.ok:
            self.history = []
        return result

    def recover(self) -> Result:
        completed, errors, remaining = [], [], []
        for move in reversed(self.pending):
            reverse = move.reverse()
            try:
                move_file(reverse)
                completed.append(reverse)
            except (OSError, ValueError) as exc:
                remaining.append(move)
                errors.append(describe_error(reverse, exc))
        self.pending = list(reversed(remaining))
        message = (f"仍有 {len(remaining)} 个文件未恢复，请查看详情"
                   if remaining else "已恢复到该批次操作前的状态")
        return Result(not remaining, message, errors, completed)
