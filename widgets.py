# widgets.py - кастомные виджеты (исправленная версия с увеличенными шрифтами)
import os
import re
from datetime import datetime
from PyQt5.QtWidgets import (QLineEdit, QDialog, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QFormLayout, QTableWidget,
                             QTableWidgetItem, QHeaderView, QAbstractItemView,
                             QMessageBox, QWidget)
from PyQt5.QtCore import Qt, QSettings, QTimer  # Добавлен QTimer
from PyQt5.QtGui import QFont, QKeyEvent
import openpyxl


class ValidatedLineEdit(QLineEdit):
    """Поле ввода с валидацией"""

    def __init__(self, validation_type='text', max_length=None, parent=None):
        super().__init__(parent)
        self.validation_type = validation_type
        if max_length:
            self.setMaxLength(max_length)
        self.setFont(QFont("Segoe UI", 14))  # Увеличенный шрифт

    def keyPressEvent(self, event):
        try:
            if self.validation_type == 'digits':
                if event.text() and not event.text().isdigit():
                    return
            elif self.validation_type == 'cyrillic_upper':
                if event.text() and not re.match(r'[А-ЯЁ]', event.text().upper()):
                    return
                # Автоматически преобразуем в верхний регистр
                if event.text():
                    from PyQt5.QtGui import QKeyEvent
                    from PyQt5.QtCore import Qt
                    event = QKeyEvent(event.type(), event.key(), event.modifiers(), event.text().upper())
            elif self.validation_type == 'date':
                if event.text() and not (event.text().isdigit() or event.text() == '.'):
                    return
                if event.text() == '.' and self.text().count('.') >= 2:
                    return

            super().keyPressEvent(event)
        except Exception as e:
            print(f"Ошибка в ValidatedLineEdit: {e}")
            super().keyPressEvent(event)


class EditRecordDialog(QDialog):
    """Диалог редактирования записи - УПРОЩЕННАЯ И БЕЗОПАСНАЯ ВЕРСИЯ"""

    def __init__(self, values, parent=None):
        super().__init__(parent)
        self.values = values.copy() if values else {}
        self.fields = {}
        self.init_ui()

    def init_ui(self):
        """Инициализация интерфейса"""
        try:
            self.setWindowTitle("Редактирование записи")
            self.setModal(True)
            self.setMinimumSize(600, 500)  # Увеличил размер диалога

            layout = QVBoxLayout(self)

            # Поля ввода
            form_widget = QWidget()
            form_layout = QFormLayout(form_widget)

            field_keys = [
                ('n', 'Фамилия'),
                ('fn', 'Имя'),
                ('mn', 'Отчество'),
                ('reg', 'Регистрация'),
                ('ps', 'Серия паспорта'),
                ('pn', 'Номер паспорта'),
                ('pi', 'Паспорт выдан'),
                ('di', 'Дата выдачи'),
                ('cs', 'Серия УЧО'),
                ('cn', 'Номер УЧО')
            ]

            for key, label in field_keys:
                try:
                    # Безопасное получение значения
                    value = str(self.values.get(key, ""))

                    if key == 'cs':
                        field = ValidatedLineEdit('cyrillic_upper', 1)
                    elif key in ['cn', 'ps', 'pn']:
                        max_len = 6 if key in ['cn', 'pn'] else 4
                        field = ValidatedLineEdit('digits', max_len)
                    elif key == 'di':
                        field = ValidatedLineEdit('date', 10)
                    else:
                        field = QLineEdit()
                        field.setFont(QFont("Segoe UI", 14))  # Увеличенный шрифт

                    field.setText(value)
                    label_widget = QLabel(label + ":")
                    label_widget.setFont(QFont("Segoe UI", 14))  # Увеличенный шрифт
                    form_layout.addRow(label_widget, field)
                    self.fields[key] = field

                except Exception as e:
                    print(f"Ошибка создания поля {key}: {e}")
                    # Создаем обычное поле в случае ошибки
                    field = QLineEdit()
                    field.setFont(QFont("Segoe UI", 14))  # Увеличенный шрифт
                    field.setText(str(self.values.get(key, "")))
                    label_widget = QLabel(label + ":")
                    label_widget.setFont(QFont("Segoe UI", 14))  # Увеличенный шрифт
                    form_layout.addRow(label_widget, field)
                    self.fields[key] = field

            layout.addWidget(form_widget)

            # Кнопки
            buttons_layout = QHBoxLayout()

            save_btn = QPushButton("Сохранить")
            save_btn.setFont(QFont("Segoe UI", 14))  # Увеличенный шрифт
            save_btn.clicked.connect(self.accept)
            buttons_layout.addWidget(save_btn)

            cancel_btn = QPushButton("Отмена")
            cancel_btn.setFont(QFont("Segoe UI", 14))  # Увеличенный шрифт
            cancel_btn.clicked.connect(self.reject)
            buttons_layout.addWidget(cancel_btn)

            layout.addLayout(buttons_layout)

        except Exception as e:
            print(f"Критическая ошибка в init_ui: {e}")
            import traceback
            print(f"Трассировка: {traceback.format_exc()}")
            # Создаем минимальный интерфейс в случае ошибки
            self.create_fallback_ui()

    def create_fallback_ui(self):
        """Создать запасной интерфейс в случае ошибки"""
        try:
            layout = QVBoxLayout(self)
            error_label = QLabel(
                "Произошла ошибка при создании формы редактирования.\nПожалуйста, закройте это окно и попробуйте снова.")
            error_label.setFont(QFont("Segoe UI", 14))  # Увеличенный шрифт
            layout.addWidget(error_label)

            close_btn = QPushButton("Закрыть")
            close_btn.setFont(QFont("Segoe UI", 14))  # Увеличенный шрифт
            close_btn.clicked.connect(self.reject)
            layout.addWidget(close_btn)
        except:
            pass

    def get_values(self):
        """Получить значения полей - БЕЗОПАСНАЯ ВЕРСИЯ"""
        try:
            values = {}
            for key, field in self.fields.items():
                try:
                    values[key] = field.text().strip()
                except Exception as e:
                    print(f"Ошибка получения значения поля {key}: {e}")
                    values[key] = ""
            return values
        except Exception as e:
            print(f"Критическая ошибка в get_values: {e}")
            return {}


class RecordsTable(QTableWidget):
    """Таблица записей с сохранением состояния"""

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setSortingEnabled(True)
        self.setFont(QFont("Segoe UI", 14))  # Увеличенный шрифт для таблицы

        # Загружаем состояние сразу после создания
        QTimer.singleShot(100, self.load_state)

    def load_state(self):
        """Загрузить состояние таблицы - УЛУЧШЕННАЯ ВЕРСИЯ"""
        try:
            print("Загрузка состояния таблицы...")

            # Загрузка размеров колонок (исключая последнюю скрытую)
            column_widths = self.settings.get_table_column_widths()
            print(f"Загруженные ширины колонок: {column_widths}")

            if column_widths and len(column_widths) >= self.columnCount() - 1:
                for col, width in enumerate(column_widths):
                    if col < self.columnCount() - 1:  # Исключаем последнюю скрытую колонку
                        self.setColumnWidth(col, width)
                        print(f"Установлена ширина колонки {col}: {width}")
            else:
                print("Нет сохраненных ширин колонок или несоответствие количества колонок")

            # Загрузка порядка сортировки
            sort_column = self.settings.get_table_sort_column()
            sort_order = self.settings.get_table_sort_order()
            print(f"Загруженная сортировка: колонка {sort_column}, порядок {sort_order}")

            if sort_column >= 0 and sort_column < self.columnCount() - 1:
                self.sortByColumn(sort_column, sort_order)
                print(f"Применена сортировка по колонке {sort_column}")
        except Exception as e:
            print(f"Ошибка загрузки состояния таблицы: {e}")

    def save_state(self):
        """Сохранить состояние таблицы - УЛУЧШЕННАЯ ВЕРСИЯ"""
        try:
            print("Сохранение состояния таблицы...")

            # Сохранение размеров колонок (исключая последнюю скрытую)
            column_widths = []
            for col in range(self.columnCount() - 1):  # Исключаем последнюю скрытую колонку
                width = self.columnWidth(col)
                column_widths.append(width)
                print(f"Сохранена ширина колонки {col}: {width}")

            self.settings.set_table_column_widths(column_widths)

            # Сохранение порядка сортировки (исключая последнюю колонку)
            sort_column = self.horizontalHeader().sortIndicatorSection()
            sort_order = self.horizontalHeader().sortIndicatorOrder()

            if sort_column < self.columnCount() - 1:  # Только если не последняя колонка
                self.settings.set_table_sort_column(sort_column)
                self.settings.set_table_sort_order(sort_order)
                print(f"Сохранена сортировка: колонка {sort_column}, порядок {sort_order}")
            else:
                print("Сортировка не сохранена (последняя колонка)")

        except Exception as e:
            print(f"Ошибка сохранения состояния таблицы: {e}")