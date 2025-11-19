# main.py - точка входа в приложение
import os
import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QSettings
from PyQt5.QtGui import QFont
from main_window import MainWindow
from settings import Settings
from theme_manager import ThemeManager


def main():
    """Точка входа в приложение"""
    app = QApplication(sys.argv)

    # Устанавливаем глобальный шрифт для всего приложения
    font = QFont("Segoe UI", 14)  # Увеличенный шрифт
    app.setFont(font)

    # Загрузка настроек
    settings = Settings()

    # Применение темы
    theme_manager = ThemeManager()
    theme_manager.apply_theme(settings.get_theme())

    # Создание и отображение главного окна
    window = MainWindow(settings, theme_manager)
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()