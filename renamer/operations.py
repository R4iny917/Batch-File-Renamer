import os
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .core import Entry, Snapshot, path_key, validate_name
from .recovery_store import RecoveryStore, RecoveryStoreError

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
    _ACTIONS = {"execute", "undo", "recover"}

    def __init__(self, store: RecoveryStore | None = None):
        self.history: list[Move] = []
        self.pending: list[Move] = []
        self.store = store
        self.active = None
        self.recovery_error = ""
        if self.store is not None:
            self._load_state()

    def _load_state(self):
        state = self.store.load()
        if state is None:
            return
        try:
            self.history = [self._move_from_state(move) for move in state["history"]]
            self.active = self._active_from_state(state["active"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RecoveryStoreError("恢复记录中的改名数据无效") from exc
        if self.active:
            self._reconcile_loaded_active()

    def _save_state(self):
        if self.store is None:
            return
        try:
            if not self.history and self.active is None:
                self.store.clear()
                return
            self.store.save({
                "schema_version": RecoveryStore.SCHEMA_VERSION,
                "history": [self._move_to_state(move) for move in self.history],
                "active": self._active_to_state(self.active),
            })
        except RecoveryStoreError:
            self.recovery_error = "恢复记录无法可靠更新，已暂停后续文件操作"
            raise

    @staticmethod
    def _move_to_state(move: Move) -> dict:
        return {
            "source": str(move.source),
            "target": str(move.target),
            "snapshot": {
                "device": move.snapshot.device,
                "inode": move.snapshot.inode,
                "size": move.snapshot.size,
                "modified": move.snapshot.modified,
                "created": move.snapshot.created,
            },
        }

    @staticmethod
    def _move_from_state(state: dict) -> Move:
        if not isinstance(state, dict) or set(state) != {"source", "target", "snapshot"}:
            raise ValueError("移动记录结构无效")
        source, target, snapshot = state["source"], state["target"], state["snapshot"]
        if not isinstance(source, str) or not isinstance(target, str):
            raise ValueError("移动路径无效")
        source, target = Path(source), Path(target)
        if not source.is_absolute() or not target.is_absolute() or source.parent != target.parent:
            raise ValueError("移动路径不受支持")
        if not isinstance(snapshot, dict) or set(snapshot) != {
                "device", "inode", "size", "modified", "created"}:
            raise ValueError("文件快照结构无效")
        if any(type(value) is not int for value in snapshot.values()):
            raise ValueError("文件快照数据无效")
        return Move(source, target, Snapshot(**snapshot))

    @classmethod
    def _active_from_state(cls, state: dict | None) -> dict | None:
        if state is None:
            return None
        if not isinstance(state, dict) or set(state) != {"action", "moves", "completed", "in_flight"}:
            raise ValueError("活动操作结构无效")
        action, moves = state["action"], state["moves"]
        completed, in_flight = state["completed"], state["in_flight"]
        if action not in cls._ACTIONS or not isinstance(moves, list):
            raise ValueError("活动操作类型无效")
        moves = [cls._move_from_state(move) for move in moves]
        if type(completed) is not int or not 0 <= completed <= len(moves):
            raise ValueError("活动操作进度无效")
        if in_flight is not None and (type(in_flight) is not int or in_flight != completed
                                      or in_flight >= len(moves)):
            raise ValueError("活动操作游标无效")
        return {"action": action, "moves": moves, "completed": completed,
                "in_flight": in_flight}

    @classmethod
    def _active_to_state(cls, active: dict | None) -> dict | None:
        if active is None:
            return None
        return {
            "action": active["action"],
            "moves": [cls._move_to_state(move) for move in active["moves"]],
            "completed": active["completed"],
            "in_flight": active["in_flight"],
        }

    @staticmethod
    def _position(move: Move) -> str | None:
        source_matches = False
        target_matches = False
        try:
            source_matches = Snapshot.capture(move.source) == move.snapshot
        except (OSError, ValueError):
            pass
        try:
            target_matches = Snapshot.capture(move.target) == move.snapshot
        except (OSError, ValueError):
            pass
        try:
            source_exists = move.source.exists()
            target_exists = move.target.exists()
        except OSError:
            return None
        if source_matches and not target_matches and not target_exists:
            return "source"
        if target_matches and not source_matches and not source_exists:
            return "target"
        return None

    def _reconcile_loaded_active(self):
        active = self.active
        moves = active["moves"]
        completed = active["completed"]
        for move in moves[:completed]:
            if self._position(move) != "target":
                self.recovery_error = "已记录完成的文件移动与磁盘状态不一致，未自动改动文件"
                return
        if active["in_flight"] is not None:
            position = self._position(moves[completed])
            if position is None:
                self.recovery_error = "中断文件的身份无法核实，未自动改动文件"
                return
            if position == "target":
                completed += 1
            active["completed"] = completed
            active["in_flight"] = None

        if active["action"] in {"undo", "recover"}:
            for move in moves[completed:]:
                if self._position(move) != "source":
                    self.recovery_error = (
                        f"待处理文件身份无法核实或目标名称已被占用：{move.source} → {move.target}。"
                        f"恢复记录保留于 {self.store.path}"
                    )
                    return

        if active["action"] == "execute":
            applied = moves[:completed]
            if len(applied) == len(moves):
                self.history = list(moves)
                self.active = None
            elif not applied:
                self.active = None
            else:
                restore = [move.reverse() for move in reversed(applied)]
                self._set_active("recover", restore)
            self._save_state()
            return

        remaining = moves[completed:]
        if active["action"] == "undo" and not remaining:
            self.history = []
            self.active = None
            self._save_state()
            return
        if active["action"] == "recover" and not remaining:
            self.active = None
            self.pending = []
            self._save_state()
            return
        active["moves"] = remaining
        active["completed"] = 0
        active["in_flight"] = None
        self.pending = list(remaining) if active["action"] == "recover" else []
        self._save_state()

    def _set_active(self, action: str, moves: list[Move], completed: int = 0,
                    in_flight: int | None = None):
        self.active = {"action": action, "moves": list(moves), "completed": completed,
                       "in_flight": in_flight}
        self.pending = list(moves) if action == "recover" else []
        self._save_state()

    @property
    def has_recovery(self) -> bool:
        return bool(self.pending or self.active or self.recovery_error)

    @property
    def recovery_action(self) -> str | None:
        if self.active is not None:
            return self.active["action"]
        return "recover" if self.pending else None

    def _run(self, moves: list[Move], label: str, action: str) -> Result:
        if self.recovery_error:
            return Result(False, "恢复记录无法安全核验，请查看错误详情", [self.recovery_error])
        if action != "recover" and self.pending:
            return Result(False, "请先完成失败批次的恢复")
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
            if action == "recover":
                self.pending = list(moves)
                self._set_active("recover", moves)
            return Result(False, f"{label}前检查未通过，未改动文件", errors)
        if action == "recover":
            self._set_active("recover", moves)
        else:
            self._set_active(action, moves)
        completed = []
        for index, move in enumerate(moves):
            self.active["in_flight"] = index
            self._save_state()
            try:
                move_file(move)
                completed.append(move)
                self.active["completed"] = index + 1
                self.active["in_flight"] = None
                self._save_state()
            except (OSError, ValueError) as exc:
                errors.append(describe_error(move, exc))
                position = self._position(move)
                if position is None:
                    self.recovery_error = "操作失败后无法确认文件位置，未自动继续恢复"
                    self._save_state()
                    return Result(False, "操作未完成，文件状态无法安全确认", errors + [self.recovery_error])
                if position == "target":
                    completed.append(move)
                    self.active["completed"] = index + 1
                self.active["in_flight"] = None
                self._save_state()
                if action == "recover":
                    if position == "target":
                        continue
                    remaining = moves[self.active["completed"]:]
                    self.pending = list(remaining)
                    self._set_active("recover", remaining)
                    return Result(False, f"仍有 {len(remaining)} 个文件未恢复，请查看详情",
                                  errors, completed)
                restore = [done.reverse() for done in reversed(completed)]
                if restore:
                    self._set_active("recover", restore)
                    rollback = self._run(restore, "恢复", "recover")
                    if not rollback.ok:
                        return Result(False, f"{label}未完成，仍有 {len(self.pending)} 个文件需要恢复",
                                      errors + rollback.errors,
                                      [move.reverse() for move in self.pending])
                else:
                    self.active = None
                    self.pending = []
                    self._save_state()
                return Result(False, f"{label}未完成，已恢复本批次的改动", errors)
        if action == "execute":
            self.history = list(moves)
        elif action == "undo":
            self.history = []
        self.active = None
        self.pending = []
        self._save_state()
        return Result(True, f"已{label} {len(completed)} 个文件", moves=completed)

    def execute(self, entries: list[Entry]) -> Result:
        if self.pending or self.active or self.recovery_error:
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
        return self._run(moves, "改名", "execute")

    def undo(self) -> Result:
        if self.pending or self.recovery_error:
            return Result(False, "请先完成失败批次的恢复")
        if self.active and self.active["action"] == "undo":
            return self._run(self.active["moves"], "撤销", "undo")
        if self.active:
            return Result(False, "请先完成失败批次的恢复")
        if not self.history:
            return Result(False, "没有可撤销的改名")
        return self._run([move.reverse() for move in reversed(self.history)], "撤销", "undo")

    def recover(self) -> Result:
        if self.recovery_error:
            return Result(False, "恢复记录无法安全核验，请查看错误详情", [self.recovery_error])
        if self.active and self.active["action"] == "recover":
            moves = self.active["moves"]
        else:
            moves = list(self.pending)
        if not moves:
            return Result(False, "当前没有待恢复的文件")
        return self._run(moves, "恢复", "recover")
