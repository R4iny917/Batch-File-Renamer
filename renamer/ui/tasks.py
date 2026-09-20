from collections.abc import Callable

from PySide6.QtCore import QObject, QThread

from ..operations import Result


class Worker(QThread):
    def __init__(self, operation: Callable[[], Result], parent: QObject):
        super().__init__(parent)
        self.operation = operation
        self.result: Result | None = None

    def run(self):
        try:
            self.result = self.operation()
        except Exception as exc:
            self.result = Result(False, "操作发生异常，请检查文件实际状态", [repr(exc)])
