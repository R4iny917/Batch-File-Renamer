import sys

from PySide6.QtCore import QLibraryInfo, QTimer, QTranslator
from PySide6.QtWidgets import QApplication

from .operations import RenameSession
from .recovery_store import RecoveryStore, RecoveryStoreError
from .ui.main_window import MainWindow
from .ui.runtime import configure_fonts, configure_platform, set_light_titlebar
from .workspace import Workspace


def create_workspace() -> Workspace:
    store = None
    try:
        store = RecoveryStore(RecoveryStore.default_path())
        session = RenameSession(store)
    except (OSError, RecoveryStoreError) as exc:
        session = RenameSession()
        session.store = store
        session.recovery_error = str(exc)
    return Workspace(session)


def main():
    configure_platform()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    configure_fonts(app)
    translator = QTranslator(app)
    if translator.load("qtbase_zh_CN", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(translator)
    window = MainWindow(create_workspace())
    window.show()
    QTimer.singleShot(0, window.prompt_startup_recovery)
    window.fit_to_available_area(window.screen().availableGeometry())
    window.windowHandle().screenChanged.connect(
        lambda screen: window.fit_to_available_area(screen.availableGeometry()))
    set_light_titlebar(window)
    return app.exec()
