# theme_manager.py - управление темами
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtCore import Qt


class ThemeManager:
    def __init__(self):
        self.app = QApplication.instance()

    def apply_theme(self, theme):
        """Применить тему оформления"""
        if theme == 'dark':
            self.apply_dark_theme()
        else:
            self.apply_light_theme()

    def apply_dark_theme(self):
        """Применить темную тему"""
        self.app.setStyle('Fusion')

        dark_palette = QPalette()

        # Настройка цветов палитры
        dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.WindowText, Qt.white)
        dark_palette.setColor(QPalette.Base, QColor(25, 25, 25))
        dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
        dark_palette.setColor(QPalette.ToolTipText, Qt.white)
        dark_palette.setColor(QPalette.Text, Qt.white)
        dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ButtonText, Qt.white)
        dark_palette.setColor(QPalette.BrightText, Qt.red)
        dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.HighlightedText, Qt.black)

        self.app.setPalette(dark_palette)

        # Дополнительные стили
        self.app.setStyleSheet("""
            QToolTip { 
                color: #ffffff; 
                background-color: #2a82da; 
                border: 1px solid white; 
            }
            QMenu::item:selected {
                background-color: #2a82da;
            }
        """)

    def apply_light_theme(self):
        """Применить светлую тему"""
        self.app.setStyle('Fusion')
        self.app.setPalette(self.app.style().standardPalette())
        self.app.setStyleSheet("")