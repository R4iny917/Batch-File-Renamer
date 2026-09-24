from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

APP_ICON = Path(__file__).resolve().parents[1] / "assets" / "app.svg"

STYLE = """
QWidget { font-family: 'Microsoft YaHei'; font-size: 14px; color: #17243B; }
QMainWindow, QWidget#content { background: #F7F9FC; }
QLabel { background: transparent; }
QLabel#title { font-size: 21px; font-weight: 700; }
QLabel#section, QLabel#rulesHeading { font-size: 15px; font-weight: 700; }
QLabel#rulesHeading { font-size: 16px; }
QLabel#groupTitle { font-size: 14px; font-weight: 700; color: #36445A; }
QLabel#sampleTitle { font-size: 13px; font-weight: 400; color: #626D7D; }
QLabel#hint, QLabel#subtitle { color: #626D7D; font-size: 13px; }
QLabel#example { color: #2864F5; font-weight: 600; }
QFrame#sample { background: #F8FAFC; border: none; border-top: 1px solid #EDF0F5; border-radius: 0; }
QLabel#subtitle { font-size: 14px; }
QFrame#panel { background: white; border: 1px solid #E1E7F0; border-radius: 10px; }
QFrame#divider { background: #EDF0F5; border: none; min-height: 1px; max-height: 1px; }
QLineEdit, QSpinBox { background: #FBFCFE; border: 1px solid #D8E0EC; border-radius: 7px;
    min-height: 36px; padding: 0 11px; selection-background-color: #3867ED; }
QLineEdit:focus, QSpinBox:focus { border: 1px solid #3867ED; background: white; }
QWidget#rulesContent, QScrollArea#rulesScroll { background: white; border: none; }
QWidget#rulesContent QLineEdit { min-height: 34px; max-height: 34px; border-radius: 6px; padding: 0 10px; }
QComboBox { background: #FBFCFE; border: 1px solid #D8E0EC; border-radius: 6px; min-height: 36px; padding-left: 10px; }
QComboBox:focus { border-color: #3867ED; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox QAbstractItemView { background: white; selection-background-color: #E9F0FF; selection-color: #2864F5; }

QPushButton { background: white; border: 1px solid #D8E0EC; border-radius: 7px;
    padding: 10px 15px; font-weight: 500; }
QPushButton:hover { background: #F0F5FF; border-color: #B6C9F8; }
QPushButton:focus { border: 1px solid #3867ED; }
QPushButton:disabled { color: #A4AFBF; background: #F4F6F9; border-color: #E5EAF1; }
QPushButton#primary { background: #2864F5; color: white; border: 1px solid #2864F5; font-weight: 600; }
QPushButton#primary:hover { background: #2055DC; }
QPushButton#primary:disabled { background: #A4BAEB; border-color: #A4BAEB; color: white; }
QPushButton#quiet { background: transparent; border: 1px solid transparent; color: #647792; padding: 7px 9px; }
QPushButton#quiet:hover { background: #F0F5FF; color: #2864F5; }
QPushButton#quiet:disabled { color: #B4BFCC; }
QPushButton#quiet[compact="true"] { font-size: 13px; padding: 3px 6px; }
QPushButton#recovery { color: #B63B49; }
QWidget#stepper { background: #F5F7FB; border: 1px solid #E1E7F0; border-radius: 7px; }
QWidget#stepper QSpinBox { border: none; background: white; border-radius: 0; padding: 0 2px; }
QPushButton#step { font-size: 20px; border: none; background: transparent; padding: 0; }
QTableWidget { background: white; border: none; selection-background-color: #EDF3FF; selection-color: #17243B; }
QHeaderView::section { background: #F7F9FC; color: #71809A; border: none; padding: 14px 12px; font-weight: 400; }
QHeaderView::section:!first { border-left: 1px solid #E5EAF1; }
QScrollBar:vertical { background: #F7F9FC; width: 8px; margin: 0; }
QScrollBar::handle:vertical { background: #CCD5E3; border-radius: 4px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QMenu { background: white; border: 1px solid #D8E0EC; padding: 5px; }
QMenu::item { padding: 8px 24px; }
QMenu::item:selected { background: #E9F0FF; }
QToolTip { background: white; color: #17243B; border: 1px solid #D8E0EC; padding: 6px; }
"""



def line_icon(name):
    paths = {
        "refresh": 'M20 7v5h-5M19 12a7 7 0 1 0-2 5',
        "trash": 'M4 6h16M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7M14 10v7',
        "file": 'M6 2h8l5 5v15H6zM14 2v6h5',
    }
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="{paths[name]}" fill="none" stroke="#71809A" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    pixmap = QPixmap(48, 48)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(QByteArray(svg.encode())).render(painter)
    painter.end()
    return QIcon(pixmap)
