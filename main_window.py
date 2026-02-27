# main_window.py - главное окно приложения (исправленная версия с асинхронной проверкой лицензии)
import os
import sys
import re
import subprocess
import json
from datetime import datetime
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QMessageBox, QFileDialog,
                             QTableWidget, QTableWidgetItem, QHeaderView, QDialog,
                             QTabWidget, QTextEdit, QProgressBar, QMenu, QAction,
                             QSplitter, QFormLayout, QGroupBox, QScrollArea, QAbstractItemView,
                             QComboBox, QApplication)
from PyQt5.QtCore import Qt, QSettings, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QIcon, QPalette, QColor, QCursor

from widgets import ValidatedLineEdit, EditRecordDialog, RecordsTable
from update_manager import UpdateManager
from license_manager import LicenseManager


class LicenseCheckThread(QThread):
    """Поток для асинхронной проверки лицензии"""
    finished = pyqtSignal(bool, int, str)

    def __init__(self, license_manager):
        super().__init__()
        self.license_manager = license_manager

    def run(self):
        is_valid, days_left, message = self.license_manager.check_license()
        self.finished.emit(is_valid, days_left, message)


class DocumentWorker(QThread):
    """Поток для создания документов"""
    progress = pyqtSignal(int)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, save_root, fields, application_path):
        super().__init__()
        self.save_root = save_root
        self.fields = fields
        self.application_path = application_path

    def run(self):
        try:
            # Импортируем docxtpl только здесь
            from docxtpl import DocxTemplate

            created_files = []

            # Создаем папку для документов
            folder_name = f"{self.fields.get('n', '')} {self.fields.get('fn', '')} {self.fields.get('mn', '')}".strip()
            folder_path = os.path.join(self.save_root, folder_name)
            os.makedirs(folder_path, exist_ok=True)

            # Путь к шаблонам
            templates_dir = self.application_path

            # Проверяем, есть ли шаблоны
            template_files = [f for f in os.listdir(templates_dir) if f.endswith('.docx')]
            if not template_files:
                self.error.emit("Шаблоны документов не найдены")
                return

            total = len(template_files)
            for i, template_file in enumerate(template_files):
                self.progress.emit(int((i / total) * 100))

                template_path = os.path.join(templates_dir, template_file)

                # Загружаем шаблон
                doc = DocxTemplate(template_path)

                # Подготавливаем контекст
                context = self.fields.copy()
                context['current_date'] = datetime.now().strftime('%d.%m.%Y')

                # Добавляем поля в верхнем регистре
                context.update({
                    'n_c': context.get('n', '').upper(),
                    'fn_c': context.get('fn', '').upper(),
                    'mn_c': context.get('mn', '').upper()
                })

                # Рендерим документ
                doc.render(context)

                # Сохраняем результат
                output_file = os.path.join(folder_path, template_file)
                doc.save(output_file)
                created_files.append(output_file)

            self.progress.emit(100)
            self.finished.emit(created_files)

        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """Главное окно приложения"""

    def __init__(self, settings, theme_manager):
        super().__init__()
        self.settings = settings
        self.theme_manager = theme_manager
        self.fields = {}
        self.records_data = []
        self.is_licensed = False
        self.license_thread = None
        self.license_check_message = None

        # Инициализация менеджеров
        self.update_manager = UpdateManager()
        self.license_manager = LicenseManager(self.get_script_dir())

        self.init_ui()
        self.load_settings()

        # Асинхронная проверка лицензии при старте
        QTimer.singleShot(100, self.async_check_license)
        QTimer.singleShot(5000, self.silent_update_check)

    def get_script_dir(self):
        """Получить директорию скрипта"""
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        else:
            return os.path.dirname(os.path.abspath(__file__))

    def init_ui(self):
        """Инициализация интерфейса"""
        self.setWindowTitle("Программа заполнения согласий и личных карточек")
        self.setGeometry(100, 100, 1200, 800)

        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Основной layout
        layout = QVBoxLayout(central_widget)

        # Создаем табы
        self.tab_widget = QTabWidget()
        self.tab_widget.setFont(QFont("Segoe UI", 14))
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        layout.addWidget(self.tab_widget)

        # Вкладка ввода данных
        input_tab = QWidget()
        self.tab_widget.addTab(input_tab, "Ввод данных")
        self.setup_input_tab(input_tab)

        # Вкладка записей
        records_tab = QWidget()
        self.tab_widget.addTab(records_tab, "Сохраненные анкеты")
        self.setup_records_tab(records_tab)

        # Вкладка настроек
        settings_tab = QWidget()
        self.tab_widget.addTab(settings_tab, "Настройки")
        self.setup_settings_tab(settings_tab)

        # Создаем меню
        self.create_menu()

        # Метка для сообщения о проверке лицензии
        self.license_check_message = QLabel("⏳ Проверка лицензии...")
        self.license_check_message.setAlignment(Qt.AlignCenter)
        self.license_check_message.setStyleSheet(
            "QLabel { background-color: #2196F3; color: white; font-weight: bold; padding: 10px; border-radius: 5px; }"
        )
        self.license_check_message.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.license_check_message.hide()
        layout.insertWidget(0, self.license_check_message)

    def on_tab_changed(self, index):
        """Обработчик смены вкладки"""
        try:
            if index == 1 and hasattr(self, 'records_table'):
                print("Переключились на вкладку с таблицей, загружаем состояние...")
                QTimer.singleShot(50, self.records_table.load_state)
        except Exception as e:
            print(f"Ошибка при смене вкладки: {e}")

    def setup_input_tab(self, parent):
        """Настройка вкладки ввода данных"""
        layout = QVBoxLayout(parent)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # Поля ввода
        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)
        form_layout.setSpacing(6)
        form_layout.setContentsMargins(5, 5, 5, 5)

        for key, label in self.get_field_keys():
            if key == 'cs':
                field = ValidatedLineEdit('cyrillic_upper', 1)
            elif key in ['cn', 'ps', 'pn']:
                max_len = 6 if key in ['cn', 'pn'] else 4
                field = ValidatedLineEdit('digits', max_len)
            elif key == 'di':
                field = ValidatedLineEdit('date', 10)
            else:
                field = QLineEdit()

            field.setFont(QFont("Segoe UI", 14))
            label_widget = QLabel(label + ":")
            label_widget.setFont(QFont("Segoe UI", 14))
            form_layout.addRow(label_widget, field)
            self.fields[key] = field

        layout.addWidget(form_widget)

        # Папка сохранения
        path_layout = QHBoxLayout()
        path_layout.setSpacing(8)

        path_label = QLabel("Папка сохранения:")
        path_label.setFont(QFont("Segoe UI", 13))
        path_layout.addWidget(path_label)

        self.save_path_edit = QLineEdit()
        self.save_path_edit.setFont(QFont("Segoe UI", 13))
        self.save_path_edit.setText(self.get_default_save_folder())
        path_layout.addWidget(self.save_path_edit)

        browse_btn = QPushButton("Выбрать...")
        browse_btn.setFont(QFont("Segoe UI", 12))
        browse_btn.clicked.connect(self.choose_folder)
        path_layout.addWidget(browse_btn)

        layout.addLayout(path_layout)

        # Кнопки действий
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)

        create_btn = QPushButton("Создать документы (все шаблоны)")
        create_btn.clicked.connect(self.create_documents)
        create_btn.setFont(QFont("Segoe UI", 13))
        create_btn.setStyleSheet("QPushButton { padding: 12px; }")
        buttons_layout.addWidget(create_btn)

        save_btn = QPushButton("Сохранить данные")
        save_btn.clicked.connect(self.save_data)
        save_btn.setFont(QFont("Segoe UI", 13))
        save_btn.setStyleSheet("QPushButton { padding: 12px; }")
        buttons_layout.addWidget(save_btn)

        excel_btn = QPushButton("Открыть Excel")
        excel_btn.clicked.connect(self.open_excel)
        excel_btn.setFont(QFont("Segoe UI", 13))
        excel_btn.setStyleSheet("QPushButton { padding: 12px; }")
        buttons_layout.addWidget(excel_btn)

        layout.addLayout(buttons_layout)

        # Прогресс-бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

    def setup_records_tab(self, parent):
        """Настройка вкладки записей"""
        layout = QVBoxLayout(parent)

        # Кнопки управления
        buttons_layout = QHBoxLayout()

        refresh_btn = QPushButton("Обновить")
        refresh_btn.setFont(QFont("Segoe UI", 14))
        refresh_btn.clicked.connect(self.load_records)
        buttons_layout.addWidget(refresh_btn)

        load_btn = QPushButton("Загрузить в форму")
        load_btn.setFont(QFont("Segoe UI", 14))
        load_btn.clicked.connect(self.load_selected_record)
        buttons_layout.addWidget(load_btn)

        edit_btn = QPushButton("Изменить")
        edit_btn.setFont(QFont("Segoe UI", 14))
        edit_btn.clicked.connect(self.edit_selected_record)
        buttons_layout.addWidget(edit_btn)

        delete_btn = QPushButton("Удалить")
        delete_btn.setFont(QFont("Segoe UI", 14))
        delete_btn.clicked.connect(self.delete_selected_record)
        buttons_layout.addWidget(delete_btn)

        layout.addLayout(buttons_layout)

        # Таблица записей
        self.records_table = RecordsTable(self.settings)
        self.records_table.setColumnCount(len(self.get_field_keys()) + 1)
        headers = [label for _, label in self.get_field_keys()] + ["RowNum"]
        self.records_table.setHorizontalHeaderLabels(headers)

        font = QFont("Segoe UI", 13)
        self.records_table.horizontalHeader().setFont(font)
        self.records_table.setFont(font)

        self.records_table.setColumnHidden(len(self.get_field_keys()), True)
        self.records_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.records_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.records_table.customContextMenuRequested.connect(self.show_records_context_menu)
        self.records_table.doubleClicked.connect(self.load_selected_record_double_click)

        layout.addWidget(self.records_table)
        self.load_records()

    def setup_settings_tab(self, parent):
        """Настройка вкладки настроек - упрощенная версия"""
        layout = QVBoxLayout(parent)

        # Группа тем
        theme_group = QGroupBox("Тема оформления")
        theme_group.setFont(QFont("Segoe UI", 12))
        theme_layout = QHBoxLayout(theme_group)

        self.light_theme_btn = QPushButton("Светлая")
        self.light_theme_btn.setFont(QFont("Segoe UI", 12))
        self.light_theme_btn.clicked.connect(lambda: self.change_theme('light'))
        theme_layout.addWidget(self.light_theme_btn)

        self.dark_theme_btn = QPushButton("Темная")
        self.dark_theme_btn.setFont(QFont("Segoe UI", 12))
        self.dark_theme_btn.clicked.connect(lambda: self.change_theme('dark'))
        theme_layout.addWidget(self.dark_theme_btn)

        layout.addWidget(theme_group)

        # Группа лицензии
        license_group = QGroupBox("Лицензия")
        license_group.setFont(QFont("Segoe UI", 13))
        license_layout = QVBoxLayout(license_group)

        # Информация о лицензии
        license_info_layout = QHBoxLayout()
        license_type_label = QLabel("Тип лицензии:")
        license_type_label.setFont(QFont("Segoe UI", 12))
        license_info_layout.addWidget(license_type_label)
        self.license_type_label = QLabel("Не активирована")
        self.license_type_label.setFont(QFont("Segoe UI", 12))
        license_info_layout.addWidget(self.license_type_label)
        license_info_layout.addStretch()

        license_days_label = QLabel("Осталось дней:")
        license_days_label.setFont(QFont("Segoe UI", 12))
        license_info_layout.addWidget(license_days_label)
        self.license_days_label = QLabel("0")
        self.license_days_label.setFont(QFont("Segoe UI", 12))
        license_info_layout.addWidget(self.license_days_label)

        license_layout.addLayout(license_info_layout)

        # Отображение ID оборудования
        hardware_layout = QHBoxLayout()
        hardware_label = QLabel("ID оборудования:")
        hardware_label.setFont(QFont("Segoe UI", 12))
        hardware_layout.addWidget(hardware_label)

        try:
            if hasattr(self, 'license_manager'):
                hardware_id = self.license_manager.get_hardware_id()
            else:
                hardware_id = "Ошибка: менеджер лицензий не инициализирован"
        except Exception as e:
            print(f"Ошибка получения hardware_id: {e}")
            hardware_id = "Ошибка получения ID"

        self.hardware_id_label = QLabel(hardware_id)
        self.hardware_id_label.setFont(QFont("Consolas", 12, QFont.Bold))
        self.hardware_id_label.setStyleSheet("QLabel { padding: 30px}")
        hardware_layout.addWidget(self.hardware_id_label)

        copy_hardware_btn = QPushButton("Копировать")
        copy_hardware_btn.setFont(QFont("Segoe UI", 11))
        copy_hardware_btn.setToolTip("Скопировать ID оборудования в буфер обмена")
        copy_hardware_btn.clicked.connect(self.copy_hardware_id)
        hardware_layout.addWidget(copy_hardware_btn)

        license_layout.addLayout(hardware_layout)

        # Поле для ввода ключа
        key_layout = QHBoxLayout()
        key_label = QLabel("Лицензионный ключ:")
        key_label.setFont(QFont("Segoe UI", 13))
        key_layout.addWidget(key_label)

        self.license_edit = QLineEdit()
        self.license_edit.setFont(QFont("Segoe UI", 13))
        self.license_edit.setPlaceholderText("Введите лицензионный ключ")
        key_layout.addWidget(self.license_edit)

        license_layout.addLayout(key_layout)

        # Кнопки лицензии
        license_buttons_layout = QHBoxLayout()

        activate_btn = QPushButton("Активировать")
        activate_btn.setFont(QFont("Segoe UI", 13))
        activate_btn.clicked.connect(self.activate_license)
        license_buttons_layout.addWidget(activate_btn)

        generate_btn = QPushButton("Получить ключ")
        generate_btn.setFont(QFont("Segoe UI", 13))
        generate_btn.setToolTip("Открыть инструкцию по получению лицензионного ключа")
        generate_btn.clicked.connect(self.show_get_license_info)
        license_buttons_layout.addWidget(generate_btn)

        license_layout.addLayout(license_buttons_layout)

        # Статус лицензии
        self.license_status_label = QLabel("Статус: Не проверено")
        self.license_status_label.setFont(QFont("Segoe UI", 13))
        license_layout.addWidget(self.license_status_label)

        layout.addWidget(license_group)

        # Группа информации
        info_group = QGroupBox("")
        info_group.setFont(QFont("Segoe UI", 13))
        info_layout = QVBoxLayout(info_group)

        about_text = QTextEdit()
        about_text.setReadOnly(True)
        about_text.setFont(QFont("Segoe UI", 12))
        # about_text.setHtml(...) закомментировано для краткости
        info_layout.addWidget(about_text)

        layout.addWidget(info_group)

        layout.addStretch()

    def create_menu(self):
        """Создание меню"""
        menubar = self.menuBar()
        menubar.setFont(QFont("Segoe UI", 12))

        # Меню Файл
        file_menu = menubar.addMenu('Файл')

        save_action = QAction('Сохранить данные', self)
        save_action.setFont(QFont("Segoe UI", 12))
        save_action.triggered.connect(self.save_data)
        file_menu.addAction(save_action)

        create_action = QAction('Создать документы', self)
        create_action.setFont(QFont("Segoe UI", 14))
        create_action.triggered.connect(self.create_documents)
        file_menu.addAction(create_action)

        file_menu.addSeparator()

        exit_action = QAction('Выход', self)
        exit_action.setFont(QFont("Segoe UI", 12))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Меню Вид
        view_menu = menubar.addMenu('Вид')

        light_theme_action = QAction('Светлая тема', self)
        light_theme_action.setFont(QFont("Segoe UI", 12))
        light_theme_action.triggered.connect(lambda: self.change_theme('light'))
        view_menu.addAction(light_theme_action)

        dark_theme_action = QAction('Темная тема', self)
        dark_theme_action.setFont(QFont("Segoe UI", 12))
        dark_theme_action.triggered.connect(lambda: self.change_theme('dark'))
        view_menu.addAction(dark_theme_action)

        # Меню Сервис
        service_menu = menubar.addMenu('Сервис')
        service_menu.addSeparator()
        license_action = QAction('Активировать лицензию', self)
        license_action.setFont(QFont("Segoe UI", 14))
        license_action.triggered.connect(self.show_license_dialog)
        service_menu.addAction(license_action)

        # Меню Справка
        help_menu = menubar.addMenu('Справка')
        about_action = QAction('О программе', self)
        about_action.setFont(QFont("Segoe UI", 14))
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def get_field_keys(self):
        """Получить ключи полей"""
        return [
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

    def load_settings(self):
        """Загрузка настроек"""
        geometry = self.settings.get_window_geometry()
        if geometry:
            self.restoreGeometry(geometry)

        state = self.settings.get_window_state()
        if state:
            self.restoreState(state)

        last_path = self.settings.get_last_save_path()
        if last_path:
            self.save_path_edit.setText(last_path)

    def save_settings(self):
        """Сохранение настроек"""
        self.settings.set_window_geometry(self.saveGeometry())
        self.settings.set_window_state(self.saveState())
        self.settings.set_last_save_path(self.save_path_edit.text())

    def get_default_save_folder(self):
        """Получить папку для сохранения по умолчанию"""
        return os.path.join(self.get_script_dir(), "документы")

    def get_excel_file_path(self):
        """Получить путь к Excel файлу"""
        return os.path.join(self.get_script_dir(), "анкеты_данные.xlsx")

    def ensure_excel_exists(self):
        """Создать файл Excel, если он не существует"""
        excel_path = self.get_excel_file_path()
        if not os.path.exists(excel_path):
            # Импортируем openpyxl только здесь
            import openpyxl
            wb = openpyxl.Workbook()
            sheet = wb.active
            for col, (_, label) in enumerate(self.get_field_keys(), 1):
                sheet.cell(row=1, column=col, value=label)
            wb.save(excel_path)

    def get_field_values(self):
        """Получить значения всех полей"""
        values = {}
        for key, field in self.fields.items():
            values[key] = field.text().strip()
        return values

    def set_field_values(self, values):
        """Установить значения полей"""
        for key, value in values.items():
            if key in self.fields:
                self.fields[key].setText(value)

    def validate_fields(self, values, exclude_row=None):
        """Проверка полей на корректность"""
        # Проверка обязательных полей
        required_fields = ['n', 'fn', 'ps', 'pn', 'pi', 'di', 'cs', 'cn']
        for key in required_fields:
            if not values.get(key):
                field_name = dict(self.get_field_keys())[key]
                return False, f"Поле '{field_name}' обязательно для заполнения."

        # Проверка паспортных данных
        ps = values.get('ps', '')
        if not (ps.isdigit() and len(ps) == 4):
            return False, "Серия паспорта должна состоять из 4 цифр"

        pn = values.get('pn', '')
        if not (pn.isdigit() and len(pn) == 6):
            return False, "Номер паспорта должен состоять из 6 цифр"

        # Проверка УЧО
        cs = values.get('cs', '')
        if not re.match(r'^[А-ЯЁ]$', cs):
            return False, "Серия УЧО должна быть одной заглавной русской буквой"

        cn = values.get('cn', '')
        if not (cn.isdigit() and len(cn) == 6):
            return False, "Номер УЧО должен состоять из 6 цифр"

        # Проверка уникальности УЧО
        if not self.is_cn_unique(cn, exclude_row):
            return False, "Номер УЧО должен быть уникальным"

        # Проверка даты
        di = values.get('di', '')
        if di:
            try:
                datetime.strptime(di, '%d.%m.%Y')
            except ValueError:
                return False, "Дата выдачи паспорта должна быть в формате ДД.ММ.ГГГГ"

        return True, ""

    def is_cn_unique(self, cn, exclude_row=None):
        """Проверить уникальность номера УЧО"""
        if not cn:
            return True

        excel_path = self.get_excel_file_path()
        if not os.path.exists(excel_path):
            return True

        try:
            import openpyxl
            wb = openpyxl.load_workbook(excel_path)
            sheet = wb.active

            cn_col = None
            for col in range(1, sheet.max_column + 1):
                if sheet.cell(row=1, column=col).value == "Номер УЧО":
                    cn_col = col
                    break

            if cn_col is None:
                return True

            for row in range(2, sheet.max_row + 1):
                if exclude_row and row == exclude_row:
                    continue
                if str(sheet.cell(row=row, column=cn_col).value) == str(cn):
                    return False

            return True
        except Exception:
            return True

    def find_row_by_fullname(self, values):
        """Найти строку по ФИО"""
        excel_path = self.get_excel_file_path()
        if not os.path.exists(excel_path):
            return None

        try:
            import openpyxl
            wb = openpyxl.load_workbook(excel_path)
            sheet = wb.active

            n_col, fn_col, mn_col = None, None, None
            for col in range(1, sheet.max_column + 1):
                header = sheet.cell(row=1, column=col).value
                if header == "Фамилия":
                    n_col = col
                elif header == "Имя":
                    fn_col = col
                elif header == "Отчество":
                    mn_col = col

            if n_col is None or fn_col is None:
                return None

            for row in range(2, sheet.max_row + 1):
                n_val = sheet.cell(row=row, column=n_col).value
                fn_val = sheet.cell(row=row, column=fn_col).value
                mn_val = sheet.cell(row=row, column=mn_col).value if mn_col else ""

                if (str(n_val) == str(values.get('n', '')) and
                        str(fn_val) == str(values.get('fn', '')) and
                        str(mn_val or '') == str(values.get('mn', ''))):
                    return row

            return None
        except Exception:
            return None

    def save_to_excel(self, values):
        """Сохранить данные в Excel"""
        try:
            import openpyxl
            excel_path = self.get_excel_file_path()
            self.ensure_excel_exists()

            wb = openpyxl.load_workbook(excel_path)
            sheet = wb.active

            # Проверяем, существует ли уже запись (для обновления)
            existing_row = values.get('_row_number')

            if existing_row:
                # Обновляем существующую запись
                for col, (key, _) in enumerate(self.get_field_keys(), 1):
                    sheet.cell(row=existing_row, column=col, value=values.get(key, ""))
                action = "обновлена"
            else:
                # Проверяем, существует ли запись с таким ФИО
                existing_row_by_name = self.find_row_by_fullname(values)

                if existing_row_by_name:
                    # Обновляем существующую запись
                    for col, (key, _) in enumerate(self.get_field_keys(), 1):
                        sheet.cell(row=existing_row_by_name, column=col, value=values.get(key, ""))
                    action = "обновлена"
                else:
                    # Добавляем новую запись
                    row_num = sheet.max_row + 1
                    for col, (key, _) in enumerate(self.get_field_keys(), 1):
                        sheet.cell(row=row_num, column=col, value=values.get(key, ""))
                    action = "добавлена"

            wb.save(excel_path)
            return True, f"Анкета успешно {action}."
        except Exception as e:
            return False, f"Ошибка при сохранении: {str(e)}"

    def get_record_by_row_number(self, row_number):
        """Найти запись по номеру строки в Excel"""
        for record in self.records_data:
            if record.get('_row_number') == row_number:
                return record
        return None

    def get_selected_record_data(self):
        """Получить данные выбранной записи с учетом сортировки"""
        try:
            selected_items = self.records_table.selectedItems()
            if not selected_items:
                return None

            visual_row = selected_items[0].row()
            row_number_item = self.records_table.item(visual_row, len(self.get_field_keys()))
            if not row_number_item:
                return None

            row_number = int(row_number_item.text())
            return self.get_record_by_row_number(row_number)

        except Exception as e:
            print(f"Ошибка получения выбранной записи: {e}")
            return None

    def load_records(self):
        """Загрузить записи в таблицу"""
        try:
            excel_path = self.get_excel_file_path()
            if not os.path.exists(excel_path):
                self.ensure_excel_exists()
                return

            import openpyxl
            wb = openpyxl.load_workbook(excel_path)
            sheet = wb.active

            # Получаем данные
            data = []
            for row in range(2, sheet.max_row + 1):
                record = {'_row_number': row}
                for col, (key, _) in enumerate(self.get_field_keys(), 1):
                    cell_value = sheet.cell(row=row, column=col).value
                    record[key] = str(cell_value) if cell_value is not None else ""
                data.append(record)

            self.records_data = data

            # Временно отключаем сортировку для заполнения
            self.records_table.setSortingEnabled(False)

            # Заполняем таблицу + добавляем скрытую колонку с номером строки
            self.records_table.setRowCount(len(data))
            for row_idx, record in enumerate(data):
                for col_idx, (key, _) in enumerate(self.get_field_keys()):
                    item = QTableWidgetItem(record.get(key, ""))
                    self.records_table.setItem(row_idx, col_idx, item)

                # Добавляем скрытую колонку с номером строки в Excel
                row_number_item = QTableWidgetItem(str(record['_row_number']))
                self.records_table.setItem(row_idx, len(self.get_field_keys()), row_number_item)

            # Включаем сортировку обратно
            self.records_table.setSortingEnabled(True)

            # После загрузки данных загружаем состояние таблицы
            QTimer.singleShot(100, self.records_table.load_state)

        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось загрузить записи: {str(e)}")

    def show_records_context_menu(self, position):
        """Показать контекстное меню для таблицы записей"""
        if not self.is_licensed:
            QMessageBox.warning(self, "Лицензия не активирована",
                                "Для работы с записями необходимо активировать лицензию.")
            return

        try:
            menu = QMenu(self)

            load_action = menu.addAction("Загрузить в форму")
            edit_action = menu.addAction("Изменить")
            delete_action = menu.addAction("Удалить")

            action = menu.exec_(self.records_table.viewport().mapToGlobal(position))

            if action == load_action:
                self.load_selected_record()
            elif action == edit_action:
                self.edit_selected_record()
            elif action == delete_action:
                self.delete_selected_record()
        except Exception as e:
            print(f"Ошибка в контекстном меню: {e}")

    def load_selected_record_double_click(self, index):
        """Загрузить запись по двойному клику"""
        try:
            self.load_selected_record()
        except Exception as e:
            print(f"Ошибка при двойном клике: {e}")

    def load_selected_record(self):
        """Загрузить выбранную запись в форму - с проверкой лицензии"""
        if not self.is_licensed:
            QMessageBox.warning(self, "Лицензия не активирована",
                                "Для загрузки записей необходимо активировать лицензию.")
            return

        try:
            record = self.get_selected_record_data()
            if not record:
                QMessageBox.warning(self, "Не выбрано", "Выберите запись для загрузки.")
                return

            self.set_field_values(record)
            QMessageBox.information(self, "Готово", "Данные загружены в форму.")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при загрузке записи: {str(e)}")

    def edit_selected_record(self):
        """Редактировать выбранную запись - с проверкой лицензии"""
        if not self.is_licensed:
            QMessageBox.warning(self, "Лицензия не активирована",
                                "Для редактирования записей необходимо активировать лицензию.")
            return

        try:
            record = self.get_selected_record_data()
            if not record:
                QMessageBox.warning(self, "Не выбрано", "Выберите запись для редактирования.")
                return

            # Создаем копию для редактирования
            values = record.copy()
            dialog = EditRecordDialog(values, self)
            if dialog.exec_() == QDialog.Accepted:
                new_values = dialog.get_values()
                new_values['_row_number'] = record.get('_row_number')

                valid, message = self.validate_fields(new_values, record.get('_row_number'))
                if not valid:
                    QMessageBox.warning(self, "Неверные данные", message)
                    return

                success, message = self.save_to_excel(new_values)
                if success:
                    QMessageBox.information(self, "Успех", message)
                    self.load_records()
                else:
                    QMessageBox.critical(self, "Ошибка", message)

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при редактировании записи: {str(e)}")

    def delete_selected_record(self):
        """Удалить выбранную запись - с проверкой лицензии"""
        if not self.is_licensed:
            QMessageBox.warning(self, "Лицензия не активирована",
                                "Для удаления записей необходимо активировать лицензию.")
            return

        try:
            record = self.get_selected_record_data()
            if not record:
                QMessageBox.warning(self, "Не выбрано", "Выберите запись для удаления.")
                return

            fio = f"{record.get('n', '')} {record.get('fn', '')} {record.get('mn', '')}".strip()
            reply = QMessageBox.question(
                self,
                "Подтверждение удаления",
                f"Удалить запись: {fio}?",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                try:
                    import openpyxl
                    excel_path = self.get_excel_file_path()
                    wb = openpyxl.load_workbook(excel_path)
                    sheet = wb.active
                    row_to_delete = record['_row_number']
                    sheet.delete_rows(row_to_delete)
                    wb.save(excel_path)

                    QMessageBox.information(self, "Удалено", "Запись удалена.")
                    self.load_records()
                except Exception as e:
                    QMessageBox.critical(self, "Ошибка", f"Не удалось удалить запись: {str(e)}")

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при удалении записи: {str(e)}")

    def choose_folder(self):
        """Выбор папки сохранения"""
        try:
            path = QFileDialog.getExistingDirectory(
                self,
                "Выберите папку",
                self.save_path_edit.text() or self.get_default_save_folder()
            )
            if path:
                self.save_path_edit.setText(path)
                self.settings.set_last_save_path(path)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при выборе папки: {str(e)}")

    def save_data(self):
        """Сохранить данные - с проверкой лицензии"""
        if not self.is_licensed:
            QMessageBox.warning(self, "Лицензия не активирована",
                                "Для сохранения данных необходимо активировать лицензию.")
            self.tab_widget.setCurrentIndex(2)
            return

        try:
            values = self.get_field_values()
            existing_row = self.find_row_by_fullname(values)
            valid, message = self.validate_fields(values, existing_row)
            if not valid:
                QMessageBox.warning(self, "Неверные данные", message)
                return

            success, message = self.save_to_excel(values)
            if success:
                QMessageBox.information(self, "Успех", message)
                self.load_records()
            else:
                QMessageBox.critical(self, "Ошибка", message)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при сохранении данных: {str(e)}")

    def create_documents(self):
        """Создать документы - с проверкой лицензии"""
        if not self.is_licensed:
            QMessageBox.warning(self, "Лицензия не активирована",
                                "Для создания документов необходимо активировать лицензию.")
            self.tab_widget.setCurrentIndex(2)
            return

        try:
            values = self.get_field_values()

            if not values.get('n') or not values.get('fn'):
                QMessageBox.warning(self, "Поля не заполнены", "Фамилия и имя обязательны.")
                return

            existing_row = self.find_row_by_fullname(values)
            if existing_row is None:
                reply = QMessageBox.question(
                    self,
                    "Сохранение анкеты",
                    f"Анкета для {values.get('n')} {values.get('fn')} {values.get('mn', '')} не найдена в базе.\n\n"
                    "Хотите сохранить её перед созданием документов?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    success, message = self.save_to_excel(values)
                    if not success:
                        QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить анкету: {message}")
                        return

            save_root = self.save_path_edit.text() or self.get_default_save_folder()
            if not os.path.isdir(save_root):
                QMessageBox.critical(self, "Ошибка", "Путь сохранения некорректен.")
                return

            self.progress_bar.setVisible(True)
            self.worker = DocumentWorker(save_root, values, self.get_script_dir())
            self.worker.progress.connect(self.progress_bar.setValue)
            self.worker.finished.connect(self.on_documents_created)
            self.worker.error.connect(self.on_documents_error)
            self.worker.start()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при создании документов: {str(e)}")

    def on_documents_created(self, created_files):
        """Обработка завершения создания документов"""
        self.progress_bar.setVisible(False)

        if created_files:
            values = self.get_field_values()
            folder_name = f"{values.get('n', '')} {values.get('fn', '')} {values.get('mn', '')}".strip()
            QMessageBox.information(
                self,
                "Готово",
                f"Создано {len(created_files)} файлов:\n\n"
                f"Папка: {folder_name}\n"
                f"Путь: {os.path.join(self.save_path_edit.text(), folder_name)}"
            )
        else:
            QMessageBox.warning(
                self,
                "Внимание",
                "Документы не созданы. Проверьте наличие шаблонов и корректность данных."
            )

    def on_documents_error(self, error_message):
        """Обработка ошибки создания документов"""
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "Ошибка", f"Ошибка при создании документов: {error_message}")

    def open_excel(self):
        """Открыть файл Excel - с проверкой лицензии"""
        if not self.is_licensed:
            QMessageBox.warning(self, "Лицензия не активирована",
                                "Для работы с Excel необходимо активировать лицензию.")
            self.tab_widget.setCurrentIndex(2)
            return

        try:
            excel_path = self.get_excel_file_path()
            if not os.path.exists(excel_path):
                self.ensure_excel_exists()

            if not os.path.exists(excel_path):
                QMessageBox.information(self, "Файл не найден", f"Файл Excel не найден по пути: {excel_path}")
                return

            if sys.platform == "win32":
                os.startfile(excel_path)
            elif sys.platform == "darwin":
                subprocess.run(['open', excel_path])
            else:
                subprocess.run(['xdg-open', excel_path])
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть файл: {e}")

    def change_theme(self, theme):
        """Изменить тему оформления"""
        try:
            self.theme_manager.apply_theme(theme)
            self.settings.set_theme(theme)
        except Exception as e:
            print(f"Ошибка при смене темы: {e}")

    def check_for_updates(self):
        """Проверить обновления - упрощенная версия"""
        try:
            print("Проверка обновлений...")
            success, result = self.update_manager.check_for_updates()

            if success:
                if result == "up_to_date":
                    QMessageBox.information(self, "Обновления",
                                            "✅ Установлена последняя версия программы.")
                else:
                    update_info = result
                    version = update_info.get('version', 'Новая версия')
                    download_url = update_info.get('download_url', '')

                    if not download_url.startswith('http'):
                        QMessageBox.warning(self, "Ошибка",
                                            f"Некорректный URL для скачивания: {download_url}")
                        return

                    reply = QMessageBox.question(
                        self,
                        "Доступно обновление",
                        f"Доступна новая версия программы: {version}\n\n"
                        f"URL: {download_url}\n\n"
                        "Установить обновление сейчас?",
                        QMessageBox.Yes | QMessageBox.No
                    )

                    if reply == QMessageBox.Yes:
                        self.install_update(update_info)
            else:
                QMessageBox.warning(self, "Обновления",
                                    f"Не удалось проверить обновления:\n{result}")

        except Exception as e:
            QMessageBox.critical(self, "Ошибка",
                                 f"Ошибка при проверке обновлений:\n{str(e)}")

    def install_update(self, update_info):
        """Установить обновление"""
        try:
            reply = QMessageBox.question(
                self,
                "Подтверждение установки",
                "Будет установлено обновление.\n\n"
                "Перед установкой будет создана резервная копия.\n"
                "Программа будет перезапущена после установки.\n\n"
                "Продолжить?",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply != QMessageBox.Yes:
                return

            progress_dialog = QMessageBox(self)
            progress_dialog.setWindowTitle("Установка обновления")
            progress_dialog.setText("Выполняется установка обновления...\nПожалуйста, подождите.")
            progress_dialog.setStandardButtons(QMessageBox.NoButton)
            progress_dialog.show()

            QTimer.singleShot(100, lambda: self.perform_update_installation(update_info, progress_dialog))

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при установке обновления:\n{str(e)}")

    def perform_update_installation(self, update_info, progress_dialog):
        """Выполнить установку обновления - С СОХРАНЕНИЕМ ГЕОМЕТРИИ"""
        try:
            geometry_file = self.save_window_geometry_for_update()
            success, message = self.update_manager.download_and_install_update(update_info, geometry_file)
            progress_dialog.close()

            if success:
                QMessageBox.information(
                    self,
                    "Обновление запущено",
                    "✅ Процесс обновления запущен!\n\n"
                    "Программа закроется и будет автоматически обновлена.\n"
                    "После обновления откроется новая версия."
                )
                self.close()
            else:
                QMessageBox.critical(
                    self,
                    "Ошибка установки",
                    f"❌ Не удалось установить обновление:\n{message}"
                )
        except Exception as e:
            progress_dialog.close()
            QMessageBox.critical(
                self,
                "Ошибка",
                f"❌ Ошибка при установке обновления:\n{str(e)}"
            )

    def activate_license(self):
        """Активировать лицензию"""
        try:
            license_key = self.license_edit.text().strip()
            if not license_key:
                QMessageBox.warning(self, "Ошибка", "Введите лицензионный ключ.")
                return

            success, message = self.license_manager.activate_license(license_key)
            if success:
                QMessageBox.information(self, "Успех", message)
                self.is_licensed = True
                self.unlock_interface()
                self.update_license_status()
                self.license_edit.clear()
            else:
                QMessageBox.critical(self, "Ошибка", message)
                self.is_licensed = False
                self.lock_interface()

            self.update_license_status()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при активации лицензии: {str(e)}")

    def show_license_dialog(self):
        """Показать диалог активации лицензии"""
        try:
            dialog = QDialog(self)
            dialog.setWindowTitle("Активация лицензии")
            dialog.setModal(True)
            dialog.resize(600, 400)

            layout = QVBoxLayout(dialog)

            hardware_id = self.license_manager.get_hardware_id()

            info_group = QGroupBox("Информация для получения ключа")
            info_group.setFont(QFont("Segoe UI", 12))
            info_layout = QVBoxLayout(info_group)

            info_text = QLabel(
                "Для получения лицензионного ключа сообщите разработчику:\n"
                f"✅ ID оборудования: {hardware_id}\n"
                "✅ Желаемый срок лицензии (1 месяц, 6 месяцев, 1 год и т.д.)"
            )
            info_text.setFont(QFont("Segoe UI", 12))
            info_text.setWordWrap(True)
            info_layout.addWidget(info_text)

            copy_id_btn = QPushButton("📋 Скопировать ID оборудования")
            copy_id_btn.setFont(QFont("Segoe UI", 12))
            copy_id_btn.clicked.connect(lambda: self.copy_hardware_id_dialog(dialog, hardware_id))
            info_layout.addWidget(copy_id_btn)

            layout.addWidget(info_group)

            activate_group = QGroupBox("Активация лицензии")
            activate_group.setFont(QFont("Segoe UI", 12))
            activate_layout = QVBoxLayout(activate_group)

            key_layout = QHBoxLayout()
            key_label = QLabel("Введите лицензионный ключ:")
            key_label.setFont(QFont("Segoe UI", 12))
            key_layout.addWidget(key_label)

            license_edit = QLineEdit()
            license_edit.setFont(QFont("Segoe UI", 12))
            license_edit.setPlaceholderText("DF-XXXXXXXX-YYYYMMDD-DDD-XXXXXXXXXXXXXXXX")
            key_layout.addWidget(license_edit)

            activate_layout.addLayout(key_layout)

            layout.addWidget(activate_group)

            buttons_layout = QHBoxLayout()

            activate_btn = QPushButton("Активировать")
            activate_btn.setFont(QFont("Segoe UI", 12))
            activate_btn.setStyleSheet("QPushButton { padding: 10px; background-color: #4CAF50; color: white; }")
            buttons_layout.addWidget(activate_btn)

            cancel_btn = QPushButton("Отмена")
            cancel_btn.setFont(QFont("Segoe UI", 12))
            cancel_btn.clicked.connect(dialog.reject)
            buttons_layout.addWidget(cancel_btn)

            layout.addLayout(buttons_layout)

            status_label = QLabel("")
            status_label.setFont(QFont("Segoe UI", 11))
            status_label.setWordWrap(True)
            layout.addWidget(status_label)

            def activate():
                key = license_edit.text().strip()
                if not key:
                    status_label.setText("❌ Введите лицензионный ключ.")
                    status_label.setStyleSheet("color: red;")
                    return

                success, message = self.license_manager.activate_license(key)
                if success:
                    status_label.setText("✅ " + message)
                    status_label.setStyleSheet("color: green;")
                    self.is_licensed = True
                    self.unlock_interface()
                    QTimer.singleShot(2000, dialog.accept)
                else:
                    status_label.setText("❌ " + message)
                    status_label.setStyleSheet("color: red;")

            activate_btn.clicked.connect(activate)

            if dialog.exec_() == QDialog.Accepted:
                self.update_license_status()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при показе диалога лицензии: {str(e)}")

    def copy_hardware_id_dialog(self, dialog, hardware_id):
        """Скопировать ID оборудования из диалога"""
        try:
            clipboard = QApplication.clipboard()
            clipboard.setText(hardware_id)
            msg = QMessageBox(dialog)
            msg.setWindowTitle("ID скопирован")
            msg.setText(f"ID оборудования скопирован в буфер обмена:\n{hardware_id}")
            msg.setIcon(QMessageBox.Information)
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()
        except Exception as e:
            QMessageBox.warning(dialog, "Ошибка", f"Не удалось скопировать ID: {e}")

    def show_about(self):
        """Показать информацию о программе"""
        try:
            from version import __version__
            QMessageBox.about(
                self,
                "О программе",
                f"Программа заполнения согласий и личных карточек\n\n"
                f"Версия: {__version__}\n\n"
                "Разработчик: Строчков Сергей Константинович\n"
                "Телефон: 8(920)791-30-43\n"
                "WhatsApp • Telegram"
            )
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при показе информации о программе: {str(e)}")

    def check_for_updates_on_startup(self):
        """Проверить обновления при запуске - тихая проверка"""
        if hasattr(self, 'update_manager'):
            QTimer.singleShot(5000, self.silent_update_check)

    def silent_update_check(self):
        """Тихая проверка обновлений без показа диалогов"""
        try:
            success, result = self.update_manager.check_for_updates()
            if success and result != "up_to_date":
                update_info = result
                version = update_info.get('version', '')
                if version.startswith('v'):
                    version = version[1:]

                msg = QMessageBox(self)
                msg.setWindowTitle("Доступно обновление")
                msg.setText(f"Доступна новая версия: {version}")
                msg.setInformativeText("Хотите установить обновление сейчас?")
                msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                msg.setDefaultButton(QMessageBox.No)

                reply = msg.exec_()
                if reply == QMessageBox.Yes:
                    self.install_update(update_info)
        except Exception as e:
            print(f"Тихая проверка обновлений: {e}")

    # === Асинхронная проверка лицензии ===
    def async_check_license(self):
        """Запустить асинхронную проверку лицензии"""
        self.show_license_check_message(True)
        self.license_thread = LicenseCheckThread(self.license_manager)
        self.license_thread.finished.connect(self.on_license_checked)
        self.license_thread.start()

    def on_license_checked(self, is_valid, days_left, message):
        """Обработка завершения проверки лицензии"""
        self.is_licensed = is_valid
        self.update_license_status()
        self.show_license_check_message(False)

        if not is_valid:
            self.lock_interface()
            # Показываем сообщение только если это не первый запуск (чтобы не дублировать)
            if hasattr(self, 'license_check_message') and self.license_check_message.isVisible():
                QMessageBox.critical(
                    self,
                    "Лицензия не действительна",
                    f"Программа не может быть запущена.\n\nПричина: {message}\n\n"
                    "Пожалуйста, активируйте лицензию во вкладке 'Настройки'."
                )
                self.tab_widget.setCurrentIndex(2)
        else:
            self.unlock_interface()

    def show_license_check_message(self, show=True):
        """Показать или скрыть сообщение о проверке лицензии"""
        if hasattr(self, 'license_check_message') and self.license_check_message:
            self.license_check_message.setVisible(show)

    def lock_interface(self):
        """Заблокировать интерфейс при отсутствии лицензии"""
        self.tab_widget.setTabEnabled(0, False)
        self.tab_widget.setTabEnabled(1, False)

        menubar = self.menuBar()
        for action in menubar.actions():
            if action.text() not in ['Сервис', 'Справка']:
                action.setEnabled(False)

        self.light_theme_btn.setEnabled(False)
        self.dark_theme_btn.setEnabled(False)

        self.show_license_required_message()

    def unlock_interface(self):
        """Разблокировать интерфейс при наличии лицензии"""
        self.tab_widget.setTabEnabled(0, True)
        self.tab_widget.setTabEnabled(1, True)
        self.tab_widget.setTabEnabled(2, True)

        menubar = self.menuBar()
        for action in menubar.actions():
            action.setEnabled(True)

        self.light_theme_btn.setEnabled(True)
        self.dark_theme_btn.setEnabled(True)

        self.hide_license_required_message()

    def show_license_required_message(self):
        """Показать сообщение о необходимости активации"""
        if hasattr(self, 'license_message_label'):
            self.license_message_label.show()
            return

        self.license_message_label = QLabel(
            "⚠️ ТРЕБУЕТСЯ АКТИВАЦИЯ ЛИЦЕНЗИИ\n"
            "Для использования программы необходимо активировать лицензию во вкладке 'Настройки'"
        )
        self.license_message_label.setAlignment(Qt.AlignCenter)
        self.license_message_label.setStyleSheet(
            "QLabel {"
            "background-color: #ffeb3b;"
            "color: #ff5722;"
            "font-weight: bold;"
            "font-size: 14px;"
            "padding: 10px;"
            "border: 2px solid #ff9800;"
            "border-radius: 5px;"
            "margin: 5px;"
            "}"
        )
        self.license_message_label.setFont(QFont("Segoe UI", 12, QFont.Bold))

        main_widget = self.centralWidget()
        main_layout = main_widget.layout()
        main_layout.insertWidget(0, self.license_message_label)

    def hide_license_required_message(self):
        """Скрыть сообщение о необходимости активации"""
        if hasattr(self, 'license_message_label'):
            self.license_message_label.hide()

    def check_license_on_startup(self):
        """Удалён – заменён на асинхронную версию"""
        pass

    def update_license_status(self):
        """Обновить статус лицензии в интерфейсе"""
        try:
            license_info = self.license_manager.get_license_info()

            is_valid = license_info['is_valid']
            days_left = license_info['days_left']
            message = license_info['message']
            license_type = license_info['type']
            is_trial = license_info.get('is_trial', False)

            if is_trial:
                self.license_type_label.setText("Пробный период")
                status_text = f"Пробный период ({days_left} дней)"
            elif license_type == 'premium':
                self.license_type_label.setText("Премиум")
                status_text = f"Премиум ({days_left} дней)"
            else:
                self.license_type_label.setText("Не активирована")
                status_text = "Не активирована"

            self.license_days_label.setText(str(days_left))

            if is_valid:
                self.license_status_label.setText(f"Статус: {status_text}")
            else:
                self.license_status_label.setText(f"Статус: {message}")

            self.settings.settings.setValue("license/is_licensed", self.is_licensed)
            self.settings.settings.setValue("license/type", license_type)
            self.settings.settings.setValue("license/days_left", days_left)
            self.settings.settings.setValue("license/is_trial", is_trial)

        except Exception as e:
            print(f"Ошибка при обновлении статуса лицензии: {e}")

    def save_window_geometry_for_update(self):
        """Сохранить геометрию окна для использования после обновления"""
        try:
            geometry = {
                "x": self.x(),
                "y": self.y(),
                "width": self.width(),
                "height": self.height(),
                "is_maximized": self.isMaximized()
            }
            geometry_file = os.path.join(self.get_script_dir(), "window_geometry.json")
            with open(geometry_file, 'w', encoding='utf-8') as f:
                json.dump(geometry, f, indent=2, ensure_ascii=False)
            print(f"✅ Геометрия окна сохранена: {geometry}")
            return geometry_file
        except Exception as e:
            print(f"❌ Ошибка сохранения геометрии окна: {e}")
            return None

    def restore_window_geometry_from_update(self):
        """Восстановить геометрию окна после обновления"""
        try:
            geometry_file = os.path.join(self.get_script_dir(), "window_geometry.json")
            if os.path.exists(geometry_file):
                import json
                with open(geometry_file, 'r', encoding='utf-8') as f:
                    geometry = json.load(f)

                if not geometry.get("is_maximized", False):
                    self.setGeometry(
                        geometry.get("x", 100),
                        geometry.get("y", 100),
                        geometry.get("width", 1200),
                        geometry.get("height", 800)
                    )
                else:
                    self.setGeometry(
                        geometry.get("x", 100),
                        geometry.get("y", 100),
                        geometry.get("width", 1200),
                        geometry.get("height", 800)
                    )
                    self.showMaximized()

                os.remove(geometry_file)
                print(f"✅ Геометрия окна восстановлена: {geometry}")
        except Exception as e:
            print(f"❌ Ошибка восстановления геометрии окна: {e}")

    def copy_hardware_id(self):
        """Скопировать ID оборудования в буфер обмена"""
        try:
            hardware_id = self.hardware_id_label.text()
            clipboard = QApplication.clipboard()
            clipboard.setText(hardware_id)
            QMessageBox.information(self, "ID скопирован",
                                    f"ID оборудования скопирован в буфер обмена:\n\n{hardware_id}\n\n"
                                    "Сообщите этот ID разработчику для получения лицензионного ключа.")
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось скопировать ID: {e}")

    def show_get_license_info(self):
        """Показать информацию о получении лицензионного ключа"""
        try:
            hardware_id = self.license_manager.get_hardware_id()
            message = f"""
📋 ДЛЯ ПОЛУЧЕНИЯ ЛИЦЕНЗИОННОГО КЛЮЧА:

1. Сообщите разработчику ID вашего оборудования:
   🔢 {hardware_id}

2. Укажите желаемый срок лицензии:
   - 1 месяц
   - 6 месяцев  
   - 1 год
   - Другой срок

3. Получите лицензионный ключ от разработчика

4. Введите ключ в поле "Лицензионный ключ" и нажмите "Активировать"

👨‍💻 КОНТАКТЫ РАЗРАБОТЧИКА:
📛 Строчков Сергей Константинович
📞 8(920)791-30-43
💬 WhatsApp • Telegram

ID оборудования можно скопировать, нажав кнопку "Копировать" выше.
"""
            QMessageBox.information(self, "Получение лицензионного ключа", message)
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось показать информацию: {e}")

    def closeEvent(self, event):
        """Обработка закрытия окна"""
        try:
            print("Сохранение состояния при закрытии приложения...")
            if hasattr(self, 'records_table'):
                print("Сохранение состояния таблицы...")
                self.records_table.save_state()

            if hasattr(self, 'license_manager'):
                license_info = self.license_manager.get_license_info()
                self.settings.settings.setValue("license/is_licensed", license_info['is_valid'])
                self.settings.settings.setValue("license/type", license_info['type'])
                self.settings.settings.setValue("license/days_left", license_info['days_left'])
                self.settings.settings.setValue("license/is_trial", license_info.get('is_trial', False))

            self.save_settings()
            print("Настройки успешно сохранены")
            event.accept()
        except Exception as e:
            print(f"Ошибка при закрытии приложения: {e}")
            event.accept()