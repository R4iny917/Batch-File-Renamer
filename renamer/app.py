import sys

from PySide6.QtCore import QLibraryInfo, QTranslator
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from .ui.main_window import MainWindow
from .ui.runtime import configure_platform, set_light_titlebar


def main():
    configure_platform()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei UI", 10))
    translator = QTranslator(app)
    if translator.load("qtbase_zh_CN", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(translator)
    window = MainWindow()
    window.show()
    window.fit_to_available_area(window.screen().availableGeometry())
    window.windowHandle().screenChanged.connect(
        lambda screen: window.fit_to_available_area(screen.availableGeometry()))
    set_light_titlebar(window)
    return app.exec()
