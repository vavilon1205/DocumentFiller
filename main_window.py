# main_window.py - главное окно приложения (исправленная версия)
import os
import sys
import re
import subprocess
from datetime import datetime
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QMessageBox, QFileDialog,
                             QTableWidget, QTableWidgetItem, QHeaderView, QDialog,
                             QTabWidget, QTextEdit, QProgressBar, QMenu, QAction,
                             QSplitter, QFormLayout, QGroupBox, QScrollArea, QAbstractItemView)
from PyQt5.QtCore import Qt, QSettings, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QIcon, QPalette, QColor, QCursor
from PyQt5 import QtCore
import openpyxl
from docxtpl import DocxTemplate

from widgets import ValidatedLineEdit, EditRecordDialog, RecordsTable
from update_manager import UpdateManager  # ИСПРАВЛЕНО: изменено с updater на update_manager
from license_manager import LicenseManager


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

                # Подготавливаем контекст - исправление для правильной подстановки ФИО
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
        self.is_licensed = False  # Флаг лицензии

        self.init_ui()
        self.load_settings()

        # Инициализация менеджеров обновлений и лицензий ПОСЛЕ init_ui
        self.update_manager = UpdateManager()
        self.license_manager = LicenseManager(self.get_script_dir())

        # АВТОМАТИЧЕСКАЯ ПРОВЕРКА ЛИЦЕНЗИИ ПРИ ЗАПУСКЕ
        self.check_license_on_startup()
        # После инициализации UI
        QTimer.singleShot(5000, self.check_for_updates_on_startup)

    def check_for_updates(self):
        """Проверить обновления - полностью переписанная версия"""
        try:
            # Проверяем, настроен ли репозиторий
            repo_info = self.update_manager.get_repository_info()
            if not repo_info['configured']:
                QMessageBox.information(
                    self,
                    "Обновления не настроены",
                    "Функция проверки обновлений не настроена.\n\n"
                    "Для настройки необходимо указать данные репозитория в файле конфигурации.",
                    QMessageBox.Ok
                )
                return

            # Создаем диалог проверки
            checking_dialog = QMessageBox(self)
            checking_dialog.setWindowTitle("Проверка обновлений")
            checking_dialog.setText("Выполняется проверка обновлений...")
            checking_dialog.setStandardButtons(QMessageBox.NoButton)
            checking_dialog.show()

            # Запускаем проверку в отдельном потоке чтобы не блокировать UI
            from PyQt5.QtCore import QThread, pyqtSignal

            class UpdateCheckThread(QThread):
                finished = pyqtSignal(object, object)

                def __init__(self, update_manager):
                    super().__init__()
                    self.update_manager = update_manager

                def run(self):
                    success, result = self.update_manager.check_for_updates()
                    self.finished.emit(success, result)

            self.update_thread = UpdateCheckThread(self.update_manager)
            self.update_thread.finished.connect(
                lambda success, result: self.on_update_check_finished(success, result, checking_dialog)
            )
            self.update_thread.start()

        except Exception as e:
            QMessageBox.critical(self, "Ошибка",
                                 f"Ошибка при проверке обновлений:\n{str(e)}")

    def on_update_check_finished(self, success, result, checking_dialog):
        """Обработчик завершения проверки обновлений"""
        checking_dialog.close()

        try:
            if not success:
                # Обработка ошибок
                error_message = self.get_user_friendly_error(result)
                QMessageBox.warning(self, "Проверка обновлений", error_message)
                return

            if result == "up_to_date":
                QMessageBox.information(self, "Проверка обновлений",
                                        "✅ Установлена последняя версия программы.")
                return

            # Обработка доступного обновления - ВАЖНО: result теперь словарь с информацией
            self.show_update_available_message(result)

        except Exception as e:
            QMessageBox.critical(self, "Ошибка",
                                 f"Ошибка при обработке результата проверки:\n{str(e)}")

    def get_user_friendly_error(self, technical_error):
        """Преобразовать техническую ошибку в понятное сообщение"""
        error_mapping = {
            "Репозиторий не настроен": "Функция обновлений не настроена.",
            "Репозиторий или релизы не найдены": "Обновления не найдены.",
            "Превышен лимит запросов": "Сервис временно недоступен.",
            "Таймаут при проверке обновлений": "Не удалось подключиться к серверу.",
            "Ошибка подключения к интернету": "Отсутствует интернет-соединение.",
            "Ошибка GitHub API": "Ошибка сервера обновлений.",
            "Ошибка сервера": "Ошибка сервера обновлений."
        }

        # Ищем совпадение в сообщении об ошибке
        for tech_error, user_error in error_mapping.items():
            if tech_error in str(technical_error):
                return user_error

        # Если не нашли совпадение, возвращаем общее сообщение
        return "Не удалось проверить обновления."

    def show_update_available_message(self, update_info):
        """Показать сообщение о доступном обновлении"""
        try:
            # Извлекаем только нужную информацию
            version = update_info.get('version', 'Новая версия')

            # Убираем префикс 'v' если есть
            if version.startswith('v'):
                version = version[1:]

            # Форматируем описание
            release_notes = update_info.get('release_notes', '').strip()
            if not release_notes:
                release_notes = "Описание изменений не предоставлено."
            else:
                # Ограничиваем длину описания
                if len(release_notes) > 250:
                    release_notes = release_notes[:250] + "..."

            # Создаем чистое сообщение без технических деталей
            message = f"Доступна новая версия программы: {version}\n\n"

            if release_notes and release_notes != "Описание изменений не предоставлено.":
                message += f"Что нового:\n{release_notes}\n\n"

            message += "Хотите установить обновление?"

            reply = QMessageBox.question(
                self,
                "Доступно обновление",
                message,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No  # По умолчанию "Нет"
            )

            if reply == QMessageBox.Yes:
                self.install_update(update_info)

        except Exception as e:
            QMessageBox.critical(self, "Ошибка",
                                 f"Ошибка при отображении информации об обновлении:\n{str(e)}")

    def install_update(self, update_info):
        """Установить обновление"""
        try:
            # Извлекаем версию для сообщения
            version = update_info.get('version', '')
            if version.startswith('v'):
                version = version[1:]

            reply = QMessageBox.question(
                self,
                "Подтверждение установки",
                f"Будет установлена версия {version}.\n\n"
                "Перед установкой будет создана резервная копия.\n"
                "Программа будет перезапущена после установки.\n\n"
                "Продолжить?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No  # По умолчанию "Нет"
            )

            if reply != QMessageBox.Yes:
                return

            # Создаем диалог прогресса
            progress_dialog = QMessageBox(self)
            progress_dialog.setWindowTitle("Установка обновления")
            progress_dialog.setText("Выполняется установка обновления...\nПожалуйста, подождите.")
            progress_dialog.setStandardButtons(QMessageBox.NoButton)
            progress_dialog.show()

            # Запускаем установку в отдельном потоке
            from PyQt5.QtCore import QThread, pyqtSignal

            class UpdateInstallThread(QThread):
                finished = pyqtSignal(object, object)

                def __init__(self, update_manager, update_info):
                    super().__init__()
                    self.update_manager = update_manager
                    self.update_info = update_info

                def run(self):
                    success, message = self.update_manager.download_and_install_update(self.update_info)
                    self.finished.emit(success, message)

            self.install_thread = UpdateInstallThread(self.update_manager, update_info)
            self.install_thread.finished.connect(
                lambda success, message: self.on_update_install_finished(success, message, progress_dialog)
            )
            self.install_thread.start()

        except Exception as e:
            QMessageBox.critical(self, "Ошибка",
                                 f"Ошибка при установке обновления:\n{str(e)}")

    def on_update_install_finished(self, success, message, progress_dialog):
        """Обработчик завершения установки обновления"""
        progress_dialog.close()

        if success:
            QMessageBox.information(
                self,
                "Обновление установлено",
                "✅ Обновление успешно установлено!\n\n"
                "Программа будет перезапущена для применения изменений."
            )
            # Даем время прочитать сообщение
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(2000, self.update_manager.restart_program)
        else:
            QMessageBox.critical(
                self,
                "Ошибка установки",
                f"❌ Не удалось установить обновление:\n{message}"
            )
    def perform_update_check(self, checking_msg):
        """Выполнить проверку обновлений - показываем только версию"""
        try:
            success, message = self.update_manager.check_for_updates()
            checking_msg.close()

            if success:
                if message == "up_to_date":
                    QMessageBox.information(self, "Проверка обновлений",
                                            "✅ Установлена последняя версия программы.")
                else:
                    # Показываем только версию без технических деталей
                    update_info = message
                    version = update_info.get('version', '')

                    # Очищаем версию от префикса 'v' если есть
                    if version.startswith('v'):
                        version = version[1:]

                    # Форматируем описание изменений
                    release_notes = update_info.get('release_notes', '').strip()
                    if not release_notes:
                        release_notes = "Описание изменений не предоставлено."
                    else:
                        # Обрезаем длинное описание
                        if len(release_notes) > 300:
                            release_notes = release_notes[:300] + "..."

                    reply = QMessageBox.question(
                        self,
                        "Доступно обновление",
                        f"Доступна новая версия программы: {version}\n\n"
                        f"Описание изменений:\n{release_notes}\n\n"
                        "Установить обновление?",
                        QMessageBox.Yes | QMessageBox.No
                    )
                    if reply == QMessageBox.Yes:
                        self.install_update(update_info)
            else:
                # Упрощенные сообщения об ошибках
                error_messages = {
                    "Репозиторий не настроен": "Функция обновлений не настроена.",
                    "Репозиторий или релизы не найдены": "Обновления не найдены.",
                    "Превышен лимит запросов": "Сервис временно недоступен.",
                    "Таймаут при проверке обновлений": "Не удалось подключиться к серверу.",
                    "Ошибка подключения к интернету": "Отсутствует интернет-соединение."
                }

                user_message = error_messages.get(message, "Не удалось проверить обновления.")
                QMessageBox.warning(self, "Проверка обновлений", user_message)

        except Exception as e:
            checking_msg.close()
            QMessageBox.critical(self, "Ошибка",
                                 f"Ошибка при проверке обновлений:\n{str(e)}")
    def manual_update_from_git(self):
        """Ручное обновление через Git"""
        return self.update_manager.perform_git_update()

    def manual_update_from_zip(self, zip_url):
        """Ручное обновление через ZIP"""
        return self.update_manager.perform_zip_update(zip_url)

    def check_for_updates_on_startup(self):
        """Проверить обновления при запуске - тихая проверка"""
        if hasattr(self, 'update_manager'):
            # Задержка чтобы не мешать запуску
            QTimer.singleShot(5000, self.silent_update_check)

    def silent_update_check(self):
        """Тихая проверка обновлений без показа диалогов"""
        try:
            success, result = self.update_manager.check_for_updates()
            if success and result != "up_to_date":
                # Показываем ненавязчивое уведомление
                update_info = result
                version = update_info.get('version', '')
                if version.startswith('v'):
                    version = version[1:]

                # Создаем кастомное сообщение
                from PyQt5.QtWidgets import QMessageBox
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
            # Игнорируем ошибки при тихой проверке
            print(f"Тихая проверка обновлений: {e}")

    def show_update_notification(self, update_info):
        """Показать уведомление о обновлении"""
        reply = QMessageBox.question(
            self,
            "Доступно обновление",
            f"Доступна новая версия {update_info.get('version', '')}\n\nУстановить обновление?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.install_update(update_info)

    def install_update(self, update_info):
        """Установить обновление - улучшенная версия"""
        try:
            # Показываем только версию в сообщении
            version = update_info.get('version', '')
            if version.startswith('v'):
                version = version[1:]

            reply = QMessageBox.question(
                self,
                "Подтверждение установки",
                f"Будет установлена версия {version}.\n\n"
                "Перед установкой будет создана резервная копия.\n"
                "Программа будет перезапущена после установки.\n\n"
                "Продолжить?",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply != QMessageBox.Yes:
                return

            # Создаем диалог прогресса
            progress_dialog = QMessageBox(self)
            progress_dialog.setWindowTitle("Установка обновления")
            progress_dialog.setText("Выполняется установка обновления...\nПожалуйста, подождите.")
            progress_dialog.setStandardButtons(QMessageBox.NoButton)
            progress_dialog.show()

            # Даем время отобразиться диалогу
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(100, lambda: self.perform_update_installation(update_info, progress_dialog))

        except Exception as e:
            QMessageBox.critical(self, "Ошибка",
                                 f"Ошибка при установке обновления:\n{str(e)}")

    def perform_update_installation(self, update_info, progress_dialog):
        """Выполнить установку обновления"""
        try:
            success, message = self.update_manager.download_and_install_update(update_info)
            progress_dialog.close()

            if success:
                QMessageBox.information(
                    self,
                    "Обновление установлено",
                    "✅ Обновление успешно установлено!\n\n"
                    "Программа будет перезапущена для применения изменений."
                )
                self.update_manager.restart_program()
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

    def get_script_dir(self):
        """Получить директорию скрипта"""
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        else:
            return os.path.dirname(os.path.abspath(__file__))

    def check_license_on_startup(self):
        """Проверить лицензию при запуске программы"""
        print("Проверка лицензии при запуске...")

        # Проверяем лицензию
        license_check = self.license_manager.check_license()
        self.is_licensed = license_check[0]

        if not self.is_licensed:
            # Лицензия не действительна - блокируем программу
            self.lock_interface()

            # Показываем критическое сообщение
            QMessageBox.critical(
                self,
                "Лицензия не действительна",
                f"Программа не может быть запущена.\n\nПричина: {license_check[2]}\n\n"
                "Пожалуйста, активируйте лицензию во вкладке 'Настройки'."
            )

            # Переходим на вкладку настроек
            self.tab_widget.setCurrentIndex(2)
        else:
            # Лицензия действительна - разблокируем интерфейс
            self.unlock_interface()

        # ОБНОВЛЯЕМ СТАТУС ЛИЦЕНЗИИ В ИНТЕРФЕЙСЕ ПРИ ЗАПУСКЕ
        self.update_license_status()

    def init_ui(self):
        """Инициализация интерфейса"""
        self.setWindowTitle("Программа заполнения согласий и личных карточек")
        self.setGeometry(100, 100, 1200, 800)  # Увеличил размер окна

        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Основной layout
        layout = QVBoxLayout(central_widget)

        # Создаем табы
        self.tab_widget = QTabWidget()
        self.tab_widget.setFont(QFont("Segoe UI", 14))  # Увеличенный шрифт для табов
        self.tab_widget.currentChanged.connect(self.on_tab_changed)  # Обработчик смены вкладки
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

    def on_tab_changed(self, index):
        """Обработчик смены вкладки"""
        try:
            # Если переключаемся на вкладку с таблицей, загружаем состояние
            if index == 1 and hasattr(self, 'records_table'):  # Вкладка "Сохраненные анкеты"
                print("Переключились на вкладку с таблицей, загружаем состояние...")
                # Используем таймер для гарантии, что таблица уже отобразилась
                QTimer.singleShot(50, self.records_table.load_state)
        except Exception as e:
            print(f"Ошибка при смене вкладки: {e}")

    def setup_input_tab(self, parent):
        """Настройка вкладки ввода данных"""
        layout = QVBoxLayout(parent)
        layout.setSpacing(8)  # Уменьшаем общее расстояние между элементами
        layout.setContentsMargins(8, 8, 8, 8)  # Уменьшаем поля

        # Поля ввода
        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)
        form_layout.setSpacing(6)  # Уменьшаем расстояние между строками формы
        form_layout.setContentsMargins(5, 5, 5, 5)  # Уменьшаем поля формы

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

        # Папка сохранения - компактная версия
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
        refresh_btn.setFont(QFont("Segoe UI", 14))  # Увеличенный шрифт
        refresh_btn.clicked.connect(self.load_records)
        buttons_layout.addWidget(refresh_btn)

        load_btn = QPushButton("Загрузить в форму")
        load_btn.setFont(QFont("Segoe UI", 14))  # Увеличенный шрифт
        load_btn.clicked.connect(self.load_selected_record)
        buttons_layout.addWidget(load_btn)

        edit_btn = QPushButton("Изменить")
        edit_btn.setFont(QFont("Segoe UI", 14))  # Увеличенный шрифт
        edit_btn.clicked.connect(self.edit_selected_record)
        buttons_layout.addWidget(edit_btn)

        delete_btn = QPushButton("Удалить")
        delete_btn.setFont(QFont("Segoe UI", 14))  # Увеличенный шрифт
        delete_btn.clicked.connect(self.delete_selected_record)
        buttons_layout.addWidget(delete_btn)

        layout.addLayout(buttons_layout)

        # Таблица записей с сортировкой и сохранением состояния
        self.records_table = RecordsTable(self.settings)

        # Добавляем +1 колонку для скрытого номера строки
        self.records_table.setColumnCount(len(self.get_field_keys()) + 1)
        headers = [label for _, label in self.get_field_keys()] + ["RowNum"]
        self.records_table.setHorizontalHeaderLabels(headers)

        # Устанавливаем увеличенный шрифт для заголовков таблицы
        font = QFont("Segoe UI", 13)
        self.records_table.horizontalHeader().setFont(font)
        self.records_table.setFont(font)  # Шрифт для содержимого таблицы

        # Скрываем последнюю колонку с номером строки
        self.records_table.setColumnHidden(len(self.get_field_keys()), True)

        self.records_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.records_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.records_table.customContextMenuRequested.connect(self.show_records_context_menu)
        self.records_table.doubleClicked.connect(self.load_selected_record_double_click)

        layout.addWidget(self.records_table)

        # Загружаем записи
        self.load_records()

    def setup_settings_tab(self, parent):
        """Настройка вкладки настроек"""
        layout = QVBoxLayout(parent)

        # Группа тем
        theme_group = QGroupBox("Тема оформления")
        theme_group.setFont(QFont("Segoe UI", 12))  # Увеличенный шрифт
        theme_layout = QHBoxLayout(theme_group)

        self.light_theme_btn = QPushButton("Светлая")
        self.light_theme_btn.setFont(QFont("Segoe UI", 12))  # Увеличенный шрифт
        self.light_theme_btn.clicked.connect(lambda: self.change_theme('light'))
        theme_layout.addWidget(self.light_theme_btn)

        self.dark_theme_btn = QPushButton("Темная")
        self.dark_theme_btn.setFont(QFont("Segoe UI", 12))  # Увеличенный шрифт
        self.dark_theme_btn.clicked.connect(lambda: self.change_theme('dark'))
        theme_layout.addWidget(self.dark_theme_btn)

        layout.addWidget(theme_group)

        # Группа лицензии
        license_group = QGroupBox("Лицензия")
        license_group.setFont(QFont("Segoe UI", 12))  # Увеличенный шрифт
        license_layout = QVBoxLayout(license_group)

        # Информация о лицензии
        license_info_layout = QHBoxLayout()
        license_type_label = QLabel("Тип лицензии:")
        license_type_label.setFont(QFont("Segoe UI", 12))  # Увеличенный шрифт
        license_info_layout.addWidget(license_type_label)
        self.license_type_label = QLabel("Не активирована")
        self.license_type_label.setFont(QFont("Segoe UI", 12))  # Увеличенный шрифт
        license_info_layout.addWidget(self.license_type_label)
        license_info_layout.addStretch()

        license_days_label = QLabel("Осталось дней:")
        license_days_label.setFont(QFont("Segoe UI", 12))  # Увеличенный шрифт
        license_info_layout.addWidget(license_days_label)
        self.license_days_label = QLabel("0")
        self.license_days_label.setFont(QFont("Segoe UI", 12))  # Увеличенный шрифт
        license_info_layout.addWidget(self.license_days_label)

        license_layout.addLayout(license_info_layout)

        # Поле для ввода ключа
        key_layout = QHBoxLayout()
        key_label = QLabel("Лицензионный ключ:")
        key_label.setFont(QFont("Segoe UI", 13))  # Увеличенный шрифт
        key_layout.addWidget(key_label)

        self.license_edit = QLineEdit()
        self.license_edit.setFont(QFont("Segoe UI", 13))  # Увеличенный шрифт
        self.license_edit.setPlaceholderText("Введите лицензионный ключ")
        key_layout.addWidget(self.license_edit)

        license_layout.addLayout(key_layout)

        # Кнопки лицензии - ТОЛЬКО АКТИВИРОВАТЬ
        license_buttons_layout = QHBoxLayout()

        activate_btn = QPushButton("Активировать")
        activate_btn.setFont(QFont("Segoe UI", 13))  # Увеличенный шрифт
        activate_btn.clicked.connect(self.activate_license)
        license_buttons_layout.addWidget(activate_btn)

        license_layout.addLayout(license_buttons_layout)

        # Статус лицензии
        self.license_status_label = QLabel("Статус: Не проверено")
        self.license_status_label.setFont(QFont("Segoe UI", 13))  # Увеличенный шрифт
        license_layout.addWidget(self.license_status_label)

        layout.addWidget(license_group)

        # Группа обновлений
        update_group = QGroupBox("Обновления")
        update_group.setFont(QFont("Segoe UI", 13))  # Увеличенный шрифт
        update_layout = QVBoxLayout(update_group)

        self.check_update_btn = QPushButton("Проверить обновления")
        self.check_update_btn.setFont(QFont("Segoe UI", 13))  # Увеличенный шрифт
        self.check_update_btn.clicked.connect(self.check_for_updates)
        update_layout.addWidget(self.check_update_btn)

        self.manual_update_btn = QPushButton("Установить обновление вручную")
        self.manual_update_btn.setFont(QFont("Segoe UI", 13))  # Увеличенный шрифт
        self.manual_update_btn.clicked.connect(self.manual_update)
        update_layout.addWidget(self.manual_update_btn)

        self.backup_btn = QPushButton("Создать резервную копию")
        self.backup_btn.setFont(QFont("Segoe UI", 13))  # Увеличенный шрифт
        self.backup_btn.clicked.connect(self.create_backup)
        update_layout.addWidget(self.backup_btn)

        self.restore_btn = QPushButton("Восстановить из копии")
        self.restore_btn.setFont(QFont("Segoe UI", 13))  # Увеличенный шрифт
        self.restore_btn.clicked.connect(self.restore_backup)
        update_layout.addWidget(self.restore_btn)

        layout.addWidget(update_group)

        # Группа информации
        info_group = QGroupBox("О программе")
        info_group.setFont(QFont("Segoe UI", 13))  # Увеличенный шрифт
        info_layout = QVBoxLayout(info_group)

        about_text = QTextEdit()
        about_text.setReadOnly(True)
        about_text.setFont(QFont("Segoe UI", 12))  # Увеличенный шрифт
        about_text.setHtml(f"""<pre style="font-family: 'Courier New', monospace; background: #f0f0f0; padding: 10px; border-radius: 5px;">
 👨‍💻 РАЗРАБОТЧИК
 📛 Строчков Сергей Константинович
 📞 8(920)791-30-43
 💬 WhatsApp • Telegram
</pre>
        """)
        info_layout.addWidget(about_text)

        layout.addWidget(info_group)
        layout.addStretch()

        # Обновляем статус лицензии (будет обновлено позже)
        self.license_status_label.setText("Статус: Инициализация...")

    def create_menu(self):
        """Создание меню"""
        menubar = self.menuBar()
        menubar.setFont(QFont("Segoe UI", 12))  # Увеличенный шрифт для меню

        # Меню Файл
        file_menu = menubar.addMenu('Файл')

        save_action = QAction('Сохранить данные', self)
        save_action.setFont(QFont("Segoe UI", 12))  # Увеличенный шрифт
        save_action.triggered.connect(self.save_data)
        file_menu.addAction(save_action)

        create_action = QAction('Создать документы', self)
        create_action.setFont(QFont("Segoe UI", 14))  # Увеличенный шрифт
        create_action.triggered.connect(self.create_documents)
        file_menu.addAction(create_action)

        file_menu.addSeparator()

        exit_action = QAction('Выход', self)
        exit_action.setFont(QFont("Segoe UI", 12))  # Увеличенный шрифт
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Меню Вид
        view_menu = menubar.addMenu('Вид')

        light_theme_action = QAction('Светлая тема', self)
        light_theme_action.setFont(QFont("Segoe UI", 12))  # Увеличенный шрифт
        light_theme_action.triggered.connect(lambda: self.change_theme('light'))
        view_menu.addAction(light_theme_action)

        dark_theme_action = QAction('Темная тема', self)
        dark_theme_action.setFont(QFont("Segoe UI", 12))  # Увеличенный шрифт
        dark_theme_action.triggered.connect(lambda: self.change_theme('dark'))
        view_menu.addAction(dark_theme_action)

        # Меню Сервис
        service_menu = menubar.addMenu('Сервис')

        update_action = QAction('Проверить обновления', self)
        update_action.setFont(QFont("Segoe UI", 14))  # Увеличенный шрифт
        update_action.triggered.connect(self.check_for_updates)
        service_menu.addAction(update_action)

        manual_update_action = QAction('Установить обновление вручную', self)
        manual_update_action.setFont(QFont("Segoe UI", 14))  # Увеличенный шрифт
        manual_update_action.triggered.connect(self.manual_update)
        service_menu.addAction(manual_update_action)

        service_menu.addSeparator()

        backup_action = QAction('Создать резервную копию', self)
        backup_action.setFont(QFont("Segoe UI", 14))  # Увеличенный шрифт
        backup_action.triggered.connect(self.create_backup)
        service_menu.addAction(backup_action)

        restore_action = QAction('Восстановить из копии', self)
        restore_action.setFont(QFont("Segoe UI", 14))  # Увеличенный шрифт
        restore_action.triggered.connect(self.restore_backup)
        service_menu.addAction(restore_action)

        service_menu.addSeparator()

        license_action = QAction('Активировать лицензию', self)
        license_action.setFont(QFont("Segoe UI", 14))  # Увеличенный шрифт
        license_action.triggered.connect(self.show_license_dialog)
        service_menu.addAction(license_action)

        # Меню Справка
        help_menu = menubar.addMenu('Справка')

        about_action = QAction('О программе', self)
        about_action.setFont(QFont("Segoe UI", 14))  # Увеличенный шрифт
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

        # Загружаем последний путь сохранения
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
            wb = openpyxl.Workbook()
            sheet = wb.active
            # Заголовки столбцов
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

            # Получаем визуальную строку
            visual_row = selected_items[0].row()

            # Получаем номер строки в Excel из скрытой колонки
            row_number_item = self.records_table.item(visual_row, len(self.get_field_keys()))
            if not row_number_item:
                return None

            row_number = int(row_number_item.text())
            return self.get_record_by_row_number(row_number)

        except Exception as e:
            print(f"Ошибка получения выбранной записи: {e}")
            return None

    def load_records(self):
        """Загрузить записи в таблицу - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        try:
            excel_path = self.get_excel_file_path()
            if not os.path.exists(excel_path):
                self.ensure_excel_exists()
                return

            wb = openpyxl.load_workbook(excel_path)
            sheet = wb.active

            # Получаем данные
            data = []
            for row in range(2, sheet.max_row + 1):
                record = {'_row_number': row}  # Сохраняем реальный номер строки в Excel
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
        """Загручить выбранную запись в форму - с проверкой лицензии"""
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

            # Создаем диалог
            dialog = EditRecordDialog(values, self)
            if dialog.exec_() == QDialog.Accepted:
                new_values = dialog.get_values()

                # Добавляем номер строки для обновления
                new_values['_row_number'] = record.get('_row_number')

                # Валидация
                valid, message = self.validate_fields(new_values, record.get('_row_number'))
                if not valid:
                    QMessageBox.warning(self, "Неверные данные", message)
                    return

                # Сохранение
                success, message = self.save_to_excel(new_values)
                if success:
                    QMessageBox.information(self, "Успех", message)
                    self.load_records()  # Перезагружаем таблицу
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

            # Получаем ФИО для подтверждения
            fio = f"{record.get('n', '')} {record.get('fn', '')} {record.get('mn', '')}".strip()

            reply = QMessageBox.question(
                self,
                "Подтверждение удаления",
                f"Удалить запись: {fio}?",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                try:
                    excel_path = self.get_excel_file_path()
                    wb = openpyxl.load_workbook(excel_path)
                    sheet = wb.active

                    # Удаляем строку (используем сохраненный номер строки)
                    row_to_delete = record['_row_number']
                    sheet.delete_rows(row_to_delete)
                    wb.save(excel_path)

                    QMessageBox.information(self, "Удалено", "Запись удалена.")
                    self.load_records()  # Перезагружаем таблицу

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
            self.tab_widget.setCurrentIndex(2)  # Переходим на вкладку настроек
            return

        try:
            values = self.get_field_values()

            # Валидация
            existing_row = self.find_row_by_fullname(values)
            valid, message = self.validate_fields(values, existing_row)
            if not valid:
                QMessageBox.warning(self, "Неверные данные", message)
                return

            # Сохранение
            success, message = self.save_to_excel(values)
            if success:
                QMessageBox.information(self, "Успех", message)
                self.load_records()  # Обновляем таблицу
            else:
                QMessageBox.critical(self, "Ошибка", message)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при сохранении данных: {str(e)}")

    def create_documents(self):
        """Создать документы - с проверкой лицензии"""
        if not self.is_licensed:
            QMessageBox.warning(self, "Лицензия не активирована",
                                "Для создания документов необходимо активировать лицензию.")
            self.tab_widget.setCurrentIndex(2)  # Переходим на вкладку настроек
            return

        try:
            values = self.get_field_values()

            # Проверка обязательных полей
            if not values.get('n') or not values.get('fn'):
                QMessageBox.warning(self, "Поля не заполнены", "Фамилия и имя обязательны.")
                return

            # Проверка существования анкеты
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

            # Проверка пути сохранения
            save_root = self.save_path_edit.text() or self.get_default_save_folder()
            if not os.path.isdir(save_root):
                QMessageBox.critical(self, "Ошибка", "Путь сохранения некорректен.")
                return

            # Запуск создания документов в отдельном потоке
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
            self.tab_widget.setCurrentIndex(2)  # Переходим на вкладку настроек
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
        """Проверить обновления"""
        try:
            success, message = self.update_manager.check_for_updates()
            if success:
                if message == "up_to_date":
                    QMessageBox.information(self, "Обновления", "У вас установлена последняя версия программы.")
                else:
                    reply = QMessageBox.question(
                        self,
                        "Доступно обновление",
                        f"Доступна новая версия: {message}\n\nУстановить обновление?",
                        QMessageBox.Yes | QMessageBox.No
                    )
                    if reply == QMessageBox.Yes:
                        self.update_manager.download_and_install_update()
            else:
                QMessageBox.warning(self, "Обновления", f"Не удалось проверить обновления: {message}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при проверке обновлений: {str(e)}")

    def manual_update(self):
        """Ручное обновление"""
        try:
            zip_file, _ = QFileDialog.getOpenFileName(
                self,
                "Выберите файл обновления (.zip)",
                "",
                "ZIP files (*.zip);;All files (*.*)"
            )

            if zip_file:
                reply = QMessageBox.question(
                    self,
                    "Подтверждение",
                    "Установить выбранное обновление? Перед установкой будет создана резервная копия.",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    success, message = self.update_manager.manual_update(zip_file)
                    if success:
                        QMessageBox.information(self, "Обновление",
                                                "Обновление успешно установлено. Программа будет перезапущена.")
                        self.update_manager.restart_program()
                    else:
                        QMessageBox.critical(self, "Ошибка обновления", message)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при ручном обновлении: {str(e)}")

    def create_backup(self):
        """Создать резервную копию"""
        try:
            success, message = self.update_manager.create_backup()
            if success:
                QMessageBox.information(self, "Резервная копия", message)
            else:
                QMessageBox.critical(self, "Ошибка", message)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при создании резервной копии: {str(e)}")

    def restore_backup(self):
        """Восстановить из резервной копии"""
        try:
            reply = QMessageBox.question(
                self,
                "Восстановление",
                "Восстановить данные из последней резервной копии?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                success, message = self.update_manager.restore_backup()
                if success:
                    QMessageBox.information(self, "Восстановление", message)
                    self.load_records()  # Перезагружаем записи
                else:
                    QMessageBox.critical(self, "Ошибка", message)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при восстановлении из резервной копии: {str(e)}")

    def lock_interface(self):
        """Заблокировать интерфейс при отсутствии лицензии"""
        # Блокируем все вкладки кроме настроек
        self.tab_widget.setTabEnabled(0, False)  # Ввод данных
        self.tab_widget.setTabEnabled(1, False)  # Сохраненные анкеты

        # Блокируем меню, кроме настроек и справки
        menubar = self.menuBar()
        for action in menubar.actions():
            if action.text() not in ['Сервис', 'Справка']:
                action.setEnabled(False)

        # Блокируем кнопки в настройках, кроме лицензии
        self.light_theme_btn.setEnabled(False)
        self.dark_theme_btn.setEnabled(False)
        self.check_update_btn.setEnabled(False)
        self.manual_update_btn.setEnabled(False)
        self.backup_btn.setEnabled(False)
        self.restore_btn.setEnabled(False)

        # Показываем сообщение о необходимости активации
        self.show_license_required_message()

    def unlock_interface(self):
        """Разблокировать интерфейс при наличии лицензии"""
        # Разблокируем все вкладки
        self.tab_widget.setTabEnabled(0, True)  # Ввод данных
        self.tab_widget.setTabEnabled(1, True)  # Сохраненные анкеты
        self.tab_widget.setTabEnabled(2, True)  # Настройки

        # Разблокируем меню
        menubar = self.menuBar()
        for action in menubar.actions():
            action.setEnabled(True)

        # Разблокируем кнопки в настройках
        self.light_theme_btn.setEnabled(True)
        self.dark_theme_btn.setEnabled(True)
        self.check_update_btn.setEnabled(True)
        self.manual_update_btn.setEnabled(True)
        self.backup_btn.setEnabled(True)
        self.restore_btn.setEnabled(True)

        # Убираем сообщение о необходимости активации
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

        # Добавляем сообщение в главный layout
        main_widget = self.centralWidget()
        main_layout = main_widget.layout()
        main_layout.insertWidget(0, self.license_message_label)

    def hide_license_required_message(self):
        """Скрыть сообщение о необходимости активации"""
        if hasattr(self, 'license_message_label'):
            self.license_message_label.hide()

    def activate_license(self):
        """Активировать лицензию - обновленная версия"""
        try:
            license_key = self.license_edit.text().strip()
            if not license_key:
                QMessageBox.warning(self, "Ошибка", "Введите лицензионный ключ.")
                return

            success, message = self.license_manager.activate_license(license_key)
            if success:
                QMessageBox.information(self, "Успех", message)
                # Автоматически разблокируем интерфейс после успешной активации
                self.is_licensed = True
                self.unlock_interface()
                # Обновляем статус лицензии
                self.update_license_status()
                # Очищаем поле ввода ключа
                self.license_edit.clear()
            else:
                QMessageBox.critical(self, "Ошибка", message)
                # Оставляем интерфейс заблокированным
                self.is_licensed = False
                self.lock_interface()

            self.update_license_status()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при активации лицензии: {str(e)}")

    def update_license_status(self):
        """Обновить статус лицензии в интерфейсе - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        try:
            license_info = self.license_manager.get_license_info()

            is_valid = license_info['is_valid']
            days_left = license_info['days_left']
            message = license_info['message']
            license_type = license_info['type']
            is_trial = license_info.get('is_trial', False)

            # Обновляем метки
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

            # Сохраняем состояние лицензии в настройках
            self.settings.settings.setValue("license/is_licensed", self.is_licensed)
            self.settings.settings.setValue("license/type", license_type)
            self.settings.settings.setValue("license/days_left", days_left)
            self.settings.settings.setValue("license/is_trial", is_trial)

        except Exception as e:
            print(f"Ошибка при обновлении статуса лицензии: {e}")

    def show_license_dialog(self):
        """Показать диалог активации лицензии"""
        try:
            dialog = QDialog(self)
            dialog.setWindowTitle("Активация лицензии")
            dialog.setModal(True)
            dialog.resize(500, 250)

            layout = QVBoxLayout(dialog)

            info_label = QLabel(
                "Для использования программы требуется активация лицензии.\n"
                "Без активированной лицензии программа будет заблокирована."
            )
            info_label.setFont(QFont("Segoe UI", 12))
            info_label.setWordWrap(True)
            layout.addWidget(info_label)

            license_layout = QHBoxLayout()
            license_label = QLabel("Лицензионный ключ:")
            license_label.setFont(QFont("Segoe UI", 12))
            license_layout.addWidget(license_label)

            license_edit = QLineEdit()
            license_edit.setFont(QFont("Segoe UI", 12))
            license_edit.setPlaceholderText("Введите лицензионный ключ...")
            license_layout.addWidget(license_edit)

            layout.addLayout(license_layout)

            buttons_layout = QHBoxLayout()
            activate_btn = QPushButton("Активировать")
            activate_btn.setFont(QFont("Segoe UI", 12))
            buttons_layout.addWidget(activate_btn)

            cancel_btn = QPushButton("Отмена")
            cancel_btn.setFont(QFont("Segoe UI", 12))
            buttons_layout.addWidget(cancel_btn)

            layout.addLayout(buttons_layout)

            status_label = QLabel("")
            status_label.setFont(QFont("Segoe UI", 11))
            status_label.setWordWrap(True)
            layout.addWidget(status_label)

            def activate():
                license_key = license_edit.text().strip()
                if not license_key:
                    status_label.setText("❌ Введите лицензионный ключ.")
                    status_label.setStyleSheet("color: red;")
                    return

                success, message = self.license_manager.activate_license(license_key)
                if success:
                    status_label.setText("✅ " + message)
                    status_label.setStyleSheet("color: green;")
                    # Автоматически разблокируем интерфейс
                    self.is_licensed = True
                    self.unlock_interface()
                    QTimer.singleShot(2000, dialog.accept)
                else:
                    status_label.setText("❌ " + message)
                    status_label.setStyleSheet("color: red;")

            activate_btn.clicked.connect(activate)
            cancel_btn.clicked.connect(dialog.reject)

            if dialog.exec_() == QDialog.Accepted:
                self.update_license_status()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при показе диалога лицензии: {str(e)}")

    def show_about(self):
        """Показать информацию о программе"""
        try:
            # Безопасное получение версии
            version = "1.0.0"
            if hasattr(self, 'update_manager'):
                try:
                    version = self.update_manager.current_version
                except Exception:
                    # Если не удалось получить версию из update_manager, пробуем из конфига
                    try:
                        version_path = os.path.join(self.get_script_dir(), 'version_config.json')
                        if os.path.exists(version_path):
                            with open(version_path, 'r', encoding='utf-8') as f:
                                version_data = json.load(f)
                                version = version_data.get('current_version', '1.0.0')
                    except:
                        pass

            QMessageBox.about(
                self,
                "О программе",
                f"Программа заполнения согласий и личных карточек\n\n"
                f"Версия: {version}\n\n"
                "Разработчик: Строчков Сергей Константинович\n"
                "Телефон: 8(920)791-30-43\n"
                "WhatsApp • Telegram"
            )
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при показе информации о программе: {str(e)}")

    def closeEvent(self, event):
        """Обработка закрытия окна - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        try:
            print("Сохранение состояния при закрытии приложения...")

            # Сохраняем состояние таблицы
            if hasattr(self, 'records_table'):
                print("Сохранение состояния таблицы...")
                self.records_table.save_state()
            else:
                print("Таблица records_table не найдена")

            # Сохраняем информацию о лицензии
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