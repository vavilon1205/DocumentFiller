# settings.py - управление настройками
from PyQt5.QtCore import QSettings, QByteArray
from PyQt5.Qt import Qt


class Settings:
    def __init__(self):
        self.settings = QSettings("MyCompany", "DocumentFiller")

    # Настройки окна
    def set_window_geometry(self, geometry):
        self.settings.setValue("window/geometry", geometry)

    def get_window_geometry(self):
        return self.settings.value("window/geometry", QByteArray())

    def set_window_state(self, state):
        self.settings.setValue("window/state", state)

    def get_window_state(self):
        return self.settings.value("window/state", QByteArray())

    def set_last_save_path(self, path):
        self.settings.setValue("paths/last_save_path", path)

    def get_last_save_path(self):
        return self.settings.value("paths/last_save_path", "")

    # Настройки темы
    def set_theme(self, theme):
        self.settings.setValue("app/theme", theme)

    def get_theme(self):
        return self.settings.value("app/theme", "light")

    # Настройки таблицы
    def set_table_column_widths(self, widths):
        self.settings.setValue("table/column_widths", widths)

    def get_table_column_widths(self):
        # Преобразуем строки в целые числа
        widths = self.settings.value("table/column_widths", [])
        if widths:
            return [int(width) for width in widths]
        return []

    def set_table_sort_column(self, column):
        self.settings.setValue("table/sort_column", column)

    def get_table_sort_column(self):
        return int(self.settings.value("table/sort_column", -1))

    def set_table_sort_order(self, order):
        self.settings.setValue("table/sort_order", order)

    def get_table_sort_order(self):
        return int(self.settings.value("table/sort_order", Qt.AscendingOrder))