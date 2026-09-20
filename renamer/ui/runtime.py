import os
import sys


def configure_platform():
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("BatchFileRenamer.Desktop")
        os.environ.setdefault("QT_QPA_PLATFORM", "windows:fontengine=directwrite")


def set_light_titlebar(widget):
    if sys.platform == "win32":
        import ctypes
        light = ctypes.c_int(0)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            ctypes.c_void_p(int(widget.winId())), 20, ctypes.byref(light), ctypes.sizeof(light))


def fit_to_available_area(window, area):
    frame_width = max(0, window.frameGeometry().width() - window.width())
    frame_height = max(40, window.frameGeometry().height() - window.height())
    width = min(1100, int(area.width() * 0.9), area.width() - frame_width - 32)
    height = min(700, int(area.height() * 0.88) - frame_height)
    window.resize(width, height)
    window.move(area.x() + (area.width() - window.width() - frame_width) // 2,
                area.y() + (area.height() - window.height() - frame_height) // 2)
