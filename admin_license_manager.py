# admin_license_manager.py - админ-приложение для управления лицензиями онлайн
import os
import sys
import json
import requests
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QMessageBox, QGroupBox, QFormLayout, QComboBox,
                             QSpinBox, QTextEdit, QTabWidget, QDialog, QDialogButtonBox,
                             QDateEdit, QCheckBox)
from PyQt5.QtCore import Qt, QTimer, QDate
from PyQt5.QtGui import QFont, QPalette, QColor


class LicenseAdminApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.license_db_url = ""  # URL к файлу базы данных на Яндекс.Диске
        self.license_data = {"users": []}
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        self.setWindowTitle("Админ-панель управления лицензиями DocumentFiller")
        self.setGeometry(100, 100, 1200, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Настройки подключения
        settings_group = QGroupBox("Настройки подключения")
        settings_layout = QFormLayout(settings_group)

        self.db_url_edit = QLineEdit()
        self.db_url_edit.setPlaceholderText("https://disk.yandex.ru/.../licenses_db.json")
        settings_layout.addRow("URL базы данных:", self.db_url_edit)

        test_btn = QPushButton("Проверить подключение")
        test_btn.clicked.connect(self.test_connection)
        settings_layout.addRow("", test_btn)

        layout.addWidget(settings_group)

        # Управление лицензиями
        self.tabs = QTabWidget()

        # Вкладка списка пользователей
        users_tab = QWidget()
        users_layout = QVBoxLayout(users_tab)

        # Кнопки управления
        users_buttons_layout = QHBoxLayout()
        refresh_btn = QPushButton("Обновить данные")
        refresh_btn.clicked.connect(self.load_license_data)
        users_buttons_layout.addWidget(refresh_btn)

        add_btn = QPushButton("Добавить лицензию")
        add_btn.clicked.connect(self.show_add_license_dialog)
        users_buttons_layout.addWidget(add_btn)

        save_btn = QPushButton("Сохранить базу")
        save_btn.clicked.connect(self.save_license_data)
        users_buttons_layout.addWidget(save_btn)

        users_buttons_layout.addStretch()
        users_layout.addLayout(users_buttons_layout)

        # Таблица пользователей
        self.users_table = QTableWidget()
        self.users_table.setColumnCount(8)
        self.users_table.setHorizontalHeaderLabels([
            "ID", "Hardware ID", "Имя", "Email", "Телефон",
            "Тип лицензии", "Действует до", "Активна"
        ])
        self.users_table.doubleClicked.connect(self.edit_license)
        users_layout.addWidget(self.users_table)

        self.tabs.addTab(users_tab, "Все лицензии")

        # Вкладка статистики
        stats_tab = QWidget()
        stats_layout = QVBoxLayout(stats_tab)

        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        stats_layout.addWidget(self.stats_text)

        self.tabs.addTab(stats_tab, "Статистика")

        layout.addWidget(self.tabs)

        # Автоматическое обновление
        self.timer = QTimer()
        self.timer.timeout.connect(self.load_license_data)
        self.timer.start(30000)  # Обновление каждые 30 секунд

    def load_settings(self):
        """Загрузить настройки"""
        try:
            if os.path.exists("admin_settings.json"):
                with open("admin_settings.json", "r", encoding="utf-8") as f:
                    settings = json.load(f)
                    self.db_url_edit.setText(settings.get("db_url", ""))
        except Exception as e:
            print(f"Ошибка загрузки настроек: {e}")

    def save_settings(self):
        """Сохранить настройки"""
        try:
            settings = {
                "db_url": self.db_url_edit.text()
            }
            with open("admin_settings.json", "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Ошибка сохранения настроек: {e}")

    def test_connection(self):
        """Проверить подключение к базе данных"""
        url = self.db_url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "Ошибка", "Введите URL базы данных")
            return

        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                QMessageBox.information(self, "Успех", "Подключение установлено успешно!")
                self.save_settings()
                self.load_license_data()
            else:
                QMessageBox.critical(self, "Ошибка", f"Ошибка подключения: {response.status_code}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка подключения: {str(e)}")

    def load_license_data(self):
        """Загрузить данные о лицензиях"""
        url = self.db_url_edit.text().strip()
        if not url:
            return

        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                self.license_data = response.json()
                self.update_users_table()
                self.update_stats()
            else:
                print(f"Ошибка загрузки данных: {response.status_code}")
        except Exception as e:
            print(f"Ошибка загрузки данных: {e}")

    def save_license_data(self):
        """Сохранить данные о лицензиях обратно на Яндекс.Диск"""
        # Для сохранения на Яндекс.Диск нужно использовать API
        # В реальном приложении здесь будет код для загрузки через API Яндекс.Диска
        QMessageBox.information(self, "Внимание",
                                "В демо-версии сохранение не реализовано.\n"
                                "В реальном приложении здесь будет загрузка на Яндекс.Диск через API.")

    def update_users_table(self):
        """Обновить таблицу пользователей"""
        users = self.license_data.get("users", [])
        self.users_table.setRowCount(len(users))

        for row, user in enumerate(users):
            # ID
            self.users_table.setItem(row, 0, QTableWidgetItem(user.get("id", "")))
            # Hardware ID
            self.users_table.setItem(row, 1, QTableWidgetItem(user.get("hardware_id", "")))
            # Имя
            self.users_table.setItem(row, 2, QTableWidgetItem(user.get("name", "")))
            # Email
            self.users_table.setItem(row, 3, QTableWidgetItem(user.get("email", "")))
            # Телефон
            self.users_table.setItem(row, 4, QTableWidgetItem(user.get("phone", "")))
            # Тип лицензии
            self.users_table.setItem(row, 5, QTableWidgetItem(user.get("license_type", "")))
            # Действует до
            expires = user.get("expires", "")
            if expires:
                try:
                    expires_date = datetime.fromisoformat(expires.replace('Z', '+00:00'))
                    expires_str = expires_date.strftime("%d.%m.%Y")
                except:
                    expires_str = expires
            else:
                expires_str = "Бессрочная"
            self.users_table.setItem(row, 6, QTableWidgetItem(expires_str))
            # Активна
            active_item = QTableWidgetItem()
            active_item.setCheckState(Qt.Checked if user.get("active", True) else Qt.Unchecked)
            self.users_table.setItem(row, 7, active_item)

        self.users_table.resizeColumnsToContents()

    def update_stats(self):
        """Обновить статистику"""
        users = self.license_data.get("users", [])
        total = len(users)
        active = sum(1 for user in users if user.get("active", True))
        premium = sum(1 for user in users if user.get("license_type") == "premium")
        trial = sum(1 for user in users if user.get("license_type") == "trial")

        # Анализ по датам
        now = datetime.now()
        expiring_soon = 0
        expired = 0
        for user in users:
            expires = user.get("expires")
            if expires:
                try:
                    expire_date = datetime.fromisoformat(expires.replace('Z', '+00:00'))
                    if expire_date < now:
                        expired += 1
                    elif (expire_date - now).days <= 30:
                        expiring_soon += 1
                except:
                    pass

        stats_text = f"""
📊 СТАТИСТИКА ЛИЦЕНЗИЙ

👥 Всего пользователей: {total}
✅ Активных лицензий: {active}
❌ Неактивных: {total - active}

🎫 Типы лицензий:
   • Премиум: {premium}
   • Пробные: {trial}
   • Стандартные: {total - premium - trial}

⏰ Сроки действия:
   • Истекших: {expired}
   • Истекают в течение 30 дней: {expiring_soon}
   • Бессрочных: {sum(1 for user in users if not user.get('expires'))}

📅 Последнее обновление: {datetime.now().strftime('%d.%m.%Y %H:%M')}
"""
        self.stats_text.setText(stats_text)

    def show_add_license_dialog(self):
        """Показать диалог добавления лицензии"""
        dialog = AddLicenseDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            new_license = dialog.get_license_data()
            self.license_data["users"].append(new_license)
            self.update_users_table()
            self.update_stats()

    def edit_license(self, index):
        """Редактировать выбранную лицензию"""
        row = index.row()
        if row < len(self.license_data["users"]):
            user = self.license_data["users"][row]
            dialog = EditLicenseDialog(user, self)
            if dialog.exec_() == QDialog.Accepted:
                updated_data = dialog.get_license_data()
                self.license_data["users"][row].update(updated_data)
                self.update_users_table()
                self.update_stats()


class AddLicenseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить лицензию")
        self.setModal(True)
        self.resize(500, 400)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        form_layout = QFormLayout()

        self.hardware_id_edit = QLineEdit()
        self.hardware_id_edit.setPlaceholderText("ABCD1234")
        form_layout.addRow("Hardware ID:", self.hardware_id_edit)

        self.name_edit = QLineEdit()
        form_layout.addRow("Имя:", self.name_edit)

        self.email_edit = QLineEdit()
        form_layout.addRow("Email:", self.email_edit)

        self.phone_edit = QLineEdit()
        form_layout.addRow("Телефон:", self.phone_edit)

        self.license_type_combo = QComboBox()
        self.license_type_combo.addItems(["premium", "standard", "trial"])
        form_layout.addRow("Тип лицензии:", self.license_type_combo)

        self.days_spinbox = QSpinBox()
        self.days_spinbox.setRange(1, 3650)
        self.days_spinbox.setValue(365)
        form_layout.addRow("Срок (дней):", self.days_spinbox)

        self.active_checkbox = QCheckBox()
        self.active_checkbox.setChecked(True)
        form_layout.addRow("Активна:", self.active_checkbox)

        layout.addLayout(form_layout)

        # Кнопки
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_license_data(self):
        """Получить данные лицензии"""
        from datetime import datetime, timedelta

        expires_date = datetime.now() + timedelta(days=self.days_spinbox.value())

        return {
            "id": str(len(self.parent().license_data["users"]) + 1),
            "hardware_id": self.hardware_id_edit.text().strip().upper(),
            "name": self.name_edit.text().strip(),
            "email": self.email_edit.text().strip(),
            "phone": self.phone_edit.text().strip(),
            "license_type": self.license_type_combo.currentText(),
            "expires": expires_date.isoformat(),
            "active": self.active_checkbox.isChecked(),
            "created": datetime.now().isoformat(),
            "last_check": datetime.now().isoformat()
        }


class EditLicenseDialog(QDialog):
    def __init__(self, user_data, parent=None):
        super().__init__(parent)
        self.user_data = user_data
        self.setWindowTitle("Редактировать лицензию")
        self.setModal(True)
        self.resize(500, 400)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        form_layout = QFormLayout()

        self.hardware_id_edit = QLineEdit(self.user_data.get("hardware_id", ""))
        self.hardware_id_edit.setReadOnly(True)
        form_layout.addRow("Hardware ID:", self.hardware_id_edit)

        self.name_edit = QLineEdit(self.user_data.get("name", ""))
        form_layout.addRow("Имя:", self.name_edit)

        self.email_edit = QLineEdit(self.user_data.get("email", ""))
        form_layout.addRow("Email:", self.email_edit)

        self.phone_edit = QLineEdit(self.user_data.get("phone", ""))
        form_layout.addRow("Телефон:", self.phone_edit)

        self.license_type_combo = QComboBox()
        self.license_type_combo.addItems(["premium", "standard", "trial"])
        self.license_type_combo.setCurrentText(self.user_data.get("license_type", "standard"))
        form_layout.addRow("Тип лицензии:", self.license_type_combo)

        # Продление лицензии
        extend_layout = QHBoxLayout()
        self.extend_days_spinbox = QSpinBox()
        self.extend_days_spinbox.setRange(1, 365)
        self.extend_days_spinbox.setValue(30)
        extend_layout.addWidget(QLabel("Продлить на:"))
        extend_layout.addWidget(self.extend_days_spinbox)
        extend_layout.addWidget(QLabel("дней"))
        extend_layout.addStretch()
        form_layout.addRow("Продление:", extend_layout)

        self.active_checkbox = QCheckBox()
        self.active_checkbox.setChecked(self.user_data.get("active", True))
        form_layout.addRow("Активна:", self.active_checkbox)

        layout.addLayout(form_layout)

        # Информация
        info_group = QGroupBox("Информация о лицензии")
        info_layout = QVBoxLayout(info_group)

        created = self.user_data.get("created", "")
        last_check = self.user_data.get("last_check", "")
        expires = self.user_data.get("expires", "")

        info_text = f"Создана: {created[:10] if created else 'Неизвестно'}\n"
        info_text += f"Последняя проверка: {last_check[:10] if last_check else 'Никогда'}\n"
        info_text += f"Истекает: {expires[:10] if expires else 'Бессрочная'}"

        info_label = QLabel(info_text)
        info_layout.addWidget(info_label)
        layout.addWidget(info_group)

        # Кнопки
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_license_data(self):
        """Получить обновленные данные лицензии"""
        from datetime import datetime, timedelta

        # Обновляем дату истечения если нужно продлить
        current_expires = self.user_data.get("expires")
        if current_expires:
            try:
                expires_date = datetime.fromisoformat(current_expires.replace('Z', '+00:00'))
                new_expires = expires_date + timedelta(days=self.extend_days_spinbox.value())
            except:
                new_expires = datetime.now() + timedelta(days=self.extend_days_spinbox.value())
        else:
            new_expires = datetime.now() + timedelta(days=self.extend_days_spinbox.value())

        return {
            "name": self.name_edit.text().strip(),
            "email": self.email_edit.text().strip(),
            "phone": self.phone_edit.text().strip(),
            "license_type": self.license_type_combo.currentText(),
            "expires": new_expires.isoformat(),
            "active": self.active_checkbox.isChecked(),
            "last_check": datetime.now().isoformat()
        }


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    # Темная тема для админки
    dark_palette = QPalette()
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
    app.setPalette(dark_palette)

    window = LicenseAdminApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()