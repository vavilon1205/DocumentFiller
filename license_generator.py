# license_generator.py - графический генератор лицензионных ключей (исправленная версия)
import sys
import os
import hashlib
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QTextEdit, QSpinBox,
                             QGroupBox, QMessageBox, QWidget, QCheckBox, QInputDialog)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


class LicenseGenerator(QMainWindow):
    def __init__(self):
        super().__init__()
        # Используем тот же ключ, что и в license_manager.py (строковый)
        self.secret_key = "document_filler_secret_2024"
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Генератор лицензионных ключей")
        self.setGeometry(300, 300, 800, 700)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        # Информация о системе
        info_group = QGroupBox("Информация о системе")
        info_group.setFont(QFont("Segoe UI", 14))
        info_layout = QVBoxLayout(info_group)

        current_hardware_id = self.get_hardware_id()
        hardware_id_label = QLabel(f"ID текущего оборудования: {current_hardware_id}")
        hardware_id_label.setFont(QFont("Consolas", 14))
        info_layout.addWidget(hardware_id_label)

        layout.addWidget(info_group)

        # Параметры лицензии
        params_group = QGroupBox("Параметры лицензии")
        params_group.setFont(QFont("Segoe UI", 14))
        params_layout = QVBoxLayout(params_group)

        # Количество дней
        days_layout = QHBoxLayout()
        days_label = QLabel("Количество дней:")
        days_label.setFont(QFont("Segoe UI", 14))
        days_layout.addWidget(days_label)
        self.days_spinbox = QSpinBox()
        self.days_spinbox.setRange(1, 3650)
        self.days_spinbox.setValue(30)
        self.days_spinbox.setFont(QFont("Segoe UI", 14))
        days_layout.addWidget(self.days_spinbox)
        days_layout.addStretch()
        params_layout.addLayout(days_layout)

        # Аппаратный ID
        hw_id_layout = QHBoxLayout()
        hw_id_label = QLabel("ID оборудования:")
        hw_id_label.setFont(QFont("Segoe UI", 14))
        hw_id_layout.addWidget(hw_id_label)
        self.hw_id_edit = QLineEdit()
        self.hw_id_edit.setText(current_hardware_id)
        self.hw_id_edit.setFont(QFont("Consolas", 14))
        self.hw_id_edit.setPlaceholderText("Введите 8-символьный ID оборудования")
        hw_id_layout.addWidget(self.hw_id_edit)
        params_layout.addLayout(hw_id_layout)

        # Чекбокс для использования текущего hardware_id
        self.use_current_hardware = QCheckBox("Использовать ID текущего оборудования")
        self.use_current_hardware.setFont(QFont("Segoe UI", 14))
        self.use_current_hardware.setChecked(True)
        self.use_current_hardware.toggled.connect(self.on_use_current_hardware_toggled)
        params_layout.addWidget(self.use_current_hardware)

        layout.addWidget(params_group)

        # Кнопки генерации
        buttons_layout = QHBoxLayout()

        generate_btn = QPushButton("Сгенерировать ключ")
        generate_btn.setFont(QFont("Segoe UI", 14))
        generate_btn.clicked.connect(self.generate_license)
        generate_btn.setStyleSheet("QPushButton { padding: 15px; background-color: #4CAF50; color: white; }")
        buttons_layout.addWidget(generate_btn)

        test_btn = QPushButton("Проверить ключ")
        test_btn.setFont(QFont("Segoe UI", 14))
        test_btn.clicked.connect(self.test_license)
        test_btn.setStyleSheet("QPushButton { padding: 15px; background-color: #2196F3; color: white; }")
        buttons_layout.addWidget(test_btn)

        clear_btn = QPushButton("Очистить")
        clear_btn.setFont(QFont("Segoe UI", 14))
        clear_btn.clicked.connect(self.clear_output)
        clear_btn.setStyleSheet("QPushButton { padding: 15px; }")
        buttons_layout.addWidget(clear_btn)

        layout.addLayout(buttons_layout)

        # Поле вывода
        output_group = QGroupBox("Сгенерированный ключ и информация")
        output_group.setFont(QFont("Segoe UI", 14))
        output_layout = QVBoxLayout(output_group)

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setFont(QFont("Consolas", 14))
        output_layout.addWidget(self.output_text)

        layout.addWidget(output_group)

        # Кнопка копирования
        copy_btn = QPushButton("Скопировать ключ в буфер обмена")
        copy_btn.setFont(QFont("Segoe UI", 14))
        copy_btn.clicked.connect(self.copy_to_clipboard)
        copy_btn.setStyleSheet("QPushButton { padding: 12px; background-color: #FF9800; color: white; }")
        layout.addWidget(copy_btn)

    def get_hardware_id(self):
        """Получить идентификатор оборудования (такой же как в license_manager.py)"""
        try:
            import platform
            import uuid

            system_info = platform.node()

            try:
                mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff)
                                for elements in range(0, 8 * 6, 8)][::-1])
                system_info += mac
            except:
                pass

            # Создаем хеш (такой же алгоритм как в license_manager.py)
            hardware_hash = hashlib.sha256(
                f"{system_info}{self.secret_key}".encode()
            ).hexdigest()[:8].upper()

            return hardware_hash

        except Exception as e:
            print(f"Ошибка получения hardware_id: {e}")
            # Резервный вариант
            backup_info = platform.node() + platform.system() + platform.architecture()[0]
            return hashlib.sha256(
                f"{backup_info}{self.secret_key}".encode()
            ).hexdigest()[:8].upper()

    def on_use_current_hardware_toggled(self, checked):
        """Обработчик переключения чекбокса использования текущего hardware_id"""
        if checked:
            current_id = self.get_hardware_id()
            self.hw_id_edit.setText(current_id)
            self.hw_id_edit.setEnabled(False)
        else:
            self.hw_id_edit.setEnabled(True)
            self.hw_id_edit.setFocus()

    def generate_license_key(self, days, hardware_id):
        """Сгенерировать лицензионный ключ (такой же алгоритм как в license_manager.py)"""
        try:
            expiration_date = datetime.now().replace(
                hour=23, minute=59, second=59, microsecond=0
            ) + timedelta(days=days)

            date_str = expiration_date.strftime('%Y%m%d')
            days_str = f"{days:03d}"

            # Формируем строку для подписи (такой же формат как в license_manager.py)
            data_string = f"{hardware_id}{date_str}{days_str}{self.secret_key}"
            signature = hashlib.sha256(data_string.encode()).hexdigest()[:16].upper()

            license_key = f"DF-{hardware_id}-{date_str}-{days_str}-{signature}"
            return license_key

        except Exception as e:
            raise Exception(f"Ошибка генерации ключа: {str(e)}")

    def validate_license_key(self, license_key):
        """Проверить валидность лицензионного ключа (такой же алгоритм как в license_manager.py)"""
        try:
            if not license_key.startswith("DF-"):
                return False, "Неверный формат лицензионного ключа"

            parts = license_key.split("-")
            if len(parts) != 5:
                return False, "Неверный формат лицензионного ключа"

            hardware_id_part = parts[1]
            date_str = parts[2]
            days_str = parts[3]
            signature = parts[4]

            try:
                expiration_date = datetime.strptime(date_str, "%Y%m%d").replace(
                    hour=23, minute=59, second=59, microsecond=0)
            except ValueError:
                return False, "Неверный формат даты в лицензионном ключе"

            try:
                days = int(days_str)
            except ValueError:
                return False, "Неверный формат количества дней"

            if datetime.now() > expiration_date:
                return False, "Срок действия лицензии истек"

            # Формируем строку для проверки подписи
            expected_data_string = f"{hardware_id_part}{date_str}{days_str}{self.secret_key}"
            expected_signature = hashlib.sha256(expected_data_string.encode()).hexdigest()[:16].upper()

            if signature != expected_signature:
                return False, "Неверная подпись лицензионного ключа"

            return True, {
                "hardware_id": hardware_id_part,
                "expiration_date": expiration_date.isoformat(),
                "days": days,
                "type": "premium"
            }

        except Exception as e:
            return False, f"Ошибка проверки лицензионного ключа: {str(e)}"

    def generate_license(self):
        try:
            days = self.days_spinbox.value()
            hardware_id = self.hw_id_edit.text().strip().upper()

            # Проверка hardware_id
            if not hardware_id:
                QMessageBox.warning(self, "Ошибка", "Введите ID оборудования")
                return

            if len(hardware_id) != 8 or not all(c in '0123456789ABCDEF' for c in hardware_id):
                QMessageBox.warning(self, "Ошибка",
                                    "ID оборудования должен состоять из 8 символов (цифры 0-9, буквы A-F)")
                return

            # Генерируем ключ
            license_key = self.generate_license_key(days, hardware_id)

            # Проверяем ключ
            is_valid, validation_result = self.validate_license_key(license_key)

            # Рассчитываем дату истечения
            expiration_date = datetime.now().replace(
                hour=23, minute=59, second=59, microsecond=0
            ) + timedelta(days=days)

            output = f"""ЛИЦЕНЗИОННЫЙ КЛЮЧ УСПЕШНО СОЗДАН
{'=' * 50}

📋 Ключ: 
{license_key}

📅 Срок действия: {days} дней
📅 Дата истечения: {expiration_date.strftime('%d.%m.%Y')}
🖥️  ID оборудования: {hardware_id}
✅ Статус проверки: {'Валиден' if is_valid else 'Невалиден'}

{'=' * 50}
ИНСТРУКЦИЯ ДЛЯ ПОЛЬЗОВАТЕЛЯ:

1. Запустите программу DocumentFiller
2. Перейдите в раздел "Настройки" → "Лицензия"
3. Введите ключ в поле "Лицензионный ключ"
4. Нажмите кнопку "Активировать"

⚠️  ВНИМАНИЕ:
• Ключ будет действителен только на оборудовании с ID: {hardware_id}
• Для активации на другом компьютере потребуется новый ключ
• Срок действия: {days} дней с момента активации
"""
            self.output_text.setPlainText(output)

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сгенерировать ключ: {str(e)}")

    def test_license(self):
        """Проверить существующий ключ"""
        key, ok = QInputDialog.getText(self, 'Проверка ключа',
                                       'Введите лицензионный ключ для проверки:')
        if ok and key:
            try:
                is_valid, result = self.validate_license_key(key.strip())
                if is_valid:
                    expiration_date = result['expiration_date'][:10]
                    days = result['days']
                    hardware_id = result['hardware_id']

                    message = f"""✅ Ключ валиден!

📅 Срок действия: {days} дней
🖥️  ID оборудования: {hardware_id}
📋 Дата истечения: {expiration_date}

Ключ может быть активирован на этом компьютере."""
                else:
                    message = f"""❌ Ключ невалиден!

Причина: {result}"""

                QMessageBox.information(self, "Результат проверки", message)
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка при проверке ключа: {str(e)}")

    def clear_output(self):
        self.output_text.clear()

    def copy_to_clipboard(self):
        text = self.output_text.toPlainText()
        if text:
            lines = text.split('\n')
            for line in lines:
                if line.startswith('DF-'):
                    key = line.strip()
                    clipboard = QApplication.clipboard()
                    clipboard.setText(key)
                    QMessageBox.information(self, "Успех", "Ключ скопирован в буфер обмена")
                    return

            for line in lines:
                if 'Ключ:' in line:
                    key = line.split('Ключ:')[1].strip()
                    clipboard = QApplication.clipboard()
                    clipboard.setText(key)
                    QMessageBox.information(self, "Успех", "Ключ скопирован в буфер обмена")
                    return

            QMessageBox.warning(self, "Внимание", "Не удалось найти ключ для копирования")


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setFont(QFont("Segoe UI", 14))

    generator = LicenseGenerator()
    generator.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()