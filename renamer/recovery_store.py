import json
import os
import tempfile
from pathlib import Path


class RecoveryStoreError(Exception):
    pass


class RecoveryStore:
    SCHEMA_VERSION = 1
    _FIELDS = {"schema_version", "history", "active"}

    def __init__(self, path: Path):
        self.path = Path(path)

    @classmethod
    def default_path(cls) -> Path:
        local_app_data = os.environ.get("LOCALAPPDATA")
        if not local_app_data:
            raise OSError("无法确定本地应用数据目录")
        return Path(local_app_data) / "Batch File Renamer" / "recovery.json"

    def load(self) -> dict | None:
        try:
            contents = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except (OSError, UnicodeError) as exc:
            raise RecoveryStoreError("无法读取恢复记录") from exc

        try:
            state = json.loads(contents)
            self._validate_state(state)
        except (json.JSONDecodeError, UnicodeError, TypeError, ValueError) as exc:
            raise RecoveryStoreError("恢复记录损坏或版本不受支持") from exc
        return state

    def save(self, state: dict) -> None:
        try:
            self._validate_state(state)
        except (TypeError, ValueError) as exc:
            raise RecoveryStoreError("恢复记录结构无效或版本不受支持") from exc
        try:
            contents = json.dumps(state, ensure_ascii=False, indent=2) + "\n"
        except (TypeError, ValueError) as exc:
            raise RecoveryStoreError("恢复记录包含无法保存的数据") from exc

        temporary_path = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                temporary.write(contents)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, self.path)
            temporary_path = None
        except OSError as exc:
            raise RecoveryStoreError("无法原子保存恢复记录") from exc
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except FileNotFoundError:
                    pass

    def clear(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise RecoveryStoreError("无法清除恢复记录") from exc

    @classmethod
    def _validate_state(cls, state: object) -> None:
        if not isinstance(state, dict) or set(state) != cls._FIELDS:
            raise ValueError("恢复记录结构无效")
        if type(state["schema_version"]) is not int or state["schema_version"] != cls.SCHEMA_VERSION:
            raise ValueError("恢复记录版本不受支持")
        if not isinstance(state["history"], list):
            raise ValueError("恢复记录历史结构无效")
        if state["active"] is not None and not isinstance(state["active"], dict):
            raise ValueError("恢复记录操作结构无效")
