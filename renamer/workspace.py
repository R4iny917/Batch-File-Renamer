from collections.abc import Iterable
from pathlib import Path

from .core import Entry, Rules, build_preview, path_key
from .operations import RenameSession, Result


class Workspace:
    def __init__(self, session: RenameSession | None = None):
        self.paths: list[Path] = []
        self.rules = Rules()
        self.rows: list[Entry] = []
        self.session = session if session is not None else RenameSession()
        self.last_result: Result | None = None

    def add_paths(self, paths: Iterable[str | Path]) -> None:
        seen = {path_key(path) for path in self.paths}
        for supplied in paths:
            path = Path(supplied).absolute()
            path = path.parent.resolve() / path.name
            if path_key(path) not in seen:
                seen.add(path_key(path))
                self.paths.append(path)
        self.refresh()

    def set_paths(self, paths: Iterable[Path]) -> None:
        self.paths = list(paths)
        self.refresh()

    def remove_rows(self, selected: set[int]) -> None:
        self.set_paths(path for index, path in enumerate(self.paths) if index not in selected)

    def set_rules(self, rules: Rules) -> None:
        self.rules = rules
        self.refresh()

    def refresh(self) -> None:
        self.rows = build_preview(self.paths, self.rules)

    def apply_result(self, result: Result, action: str) -> None:
        self.last_result = result
        mapping = {path_key(move.source): move.target for move in result.moves}
        self.paths = [mapping.get(path_key(path), path) for path in self.paths]
        if result.ok and action == "execute" and result.moves:
            self.rules = Rules()
        self.refresh()
