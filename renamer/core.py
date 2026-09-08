import os
import re
import stat
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path


@dataclass(frozen=True)
class Rules:
    find: str = ""
    replace: str = ""
    prefix: str = ""
    suffix: str = ""
    numbering: bool = False
    start: int = 1
    digits: int = 3


@dataclass(frozen=True)
class Snapshot:
    device: int
    inode: int
    size: int
    modified: int
    created: int

    @classmethod
    def capture(cls, path: Path):
        return cls.from_stat(path.lstat())

    @classmethod
    def from_stat(cls, info):
        if not stat.S_ISREG(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("仅支持普通文件，不支持目录、链接或云端占位文件")
        return cls(info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns,
                   getattr(info, "st_birthtime_ns", 0))


@dataclass(frozen=True)
class Entry:
    source: Path
    target: Path
    snapshot: Snapshot | None
    error: str = ""

    @property
    def changed(self):
        return self.source.name != self.target.name


def path_key(path: Path) -> str:
    return str(path.absolute()).casefold()


def validate_name(name: str):
    if not name or name in {".", ".."}:
        raise ValueError("文件名不能为空")
    if re.search(r'[<>:"/\\|?*\x00-\x1f]', name):
        raise ValueError("文件名包含 Windows 禁用字符")
    if name.endswith((" ", ".")):
        raise ValueError("文件名不能以空格或点结尾")
    base = name.split(".")[0].rstrip(" ").upper()
    if base in {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"} or re.fullmatch(r"(?:COM|LPT)[1-9¹²³]", base):
        raise ValueError("文件名是 Windows 保留设备名")
    if len(name.encode("utf-16-le")) // 2 > 255:
        raise ValueError("文件名超过 255 个 UTF-16 单位")


def make_name(name: str, rules: Rules, index: int) -> str:
    stem, extension = os.path.splitext(name)
    if rules.find:
        stem = stem.replace(rules.find, rules.replace)
    stem = rules.prefix + stem + rules.suffix
    if rules.numbering:
        if rules.start < 0 or not 1 <= rules.digits <= 8:
            raise ValueError("编号起始值必须非负，位数应在 1–8 之间")
        stem += f"_{rules.start + index:0{rules.digits}d}"
    if not stem:
        raise ValueError("文件名主体不能为空")
    result = stem + extension
    validate_name(result)
    return result


def build_preview(paths, rules: Rules) -> list[Entry]:
    rows = []
    directories = {}
    for index, supplied in enumerate(paths):
        source = Path(supplied).absolute()
        target, snapshot, error = source, None, ""
        try:
            source = source.parent.resolve(strict=True) / source.name
            target = source
            snapshot = Snapshot.capture(source)
            target = source.with_name(make_name(source.name, rules, index))
            if source.name != target.name:
                if source.name.casefold() == target.name.casefold():
                    raise ValueError("第一版不支持仅修改大小写")
                if source.parent not in directories:
                    directories[source.parent] = {p.name.casefold() for p in source.parent.iterdir()}
                if target.name.casefold() in directories[source.parent]:
                    raise ValueError("目标名称已被占用")
        except (OSError, ValueError) as exc:
            error = str(exc)
        rows.append(Entry(source, target, snapshot, error))
    targets = Counter(path_key(row.target) for row in rows)
    sources = Counter(path_key(row.source) for row in rows)
    return [replace(row, error=row.error or "本批次存在重复的源文件或目标名称")
            if targets[path_key(row.target)] > 1 or sources[path_key(row.source)] > 1 else row
            for row in rows]
