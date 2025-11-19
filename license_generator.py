# license_generator.py - графический генератор лицензионных ключей (исправленная версия с увеличенными шрифтами)
import sys
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QTextEdit, QSpinBox,
                             QGroupBox, QMessageBox, QWidget, QCheckBox, QInputDialog)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from license_manager import LicenseManager


class LicenseGenerator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.license_manager = LicenseManager(os.path.dirname(os.path.abspath(__file__)))
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Генератор лицензионных ключей")
        self.setGeometry(300, 300, 800, 700)  # Увеличил размер окна

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        # Информация о системе
        info_group = QGroupBox("Информация о системе")
        info_group.setFont(QFont("Segoe UI", 14))  # Увеличенный шрифт
        info_layout = QVBoxLayout(info_group)

        current_hardware_id = self.license_manager.get_hardware_id()
        hardware_id_label = QLabel(f"ID текущего оборудования: {current_hardware_id}")
        hardware_id_label.setFont(QFont("Consolas", 14))  # Увеличенный шрифт
        info_layout.addWidget(hardware_id_label)

        layout.addWidget(info_group)

        # Параметры лицензии
        params_group = QGroupBox("Параметры лицензии")
        params_group.setFont(QFont("Segoe UI", 14))  # Увеличенный шрифт
        params_layout = QVBoxLayout(params_group)

        # Количество дней
        days_layout = QHBoxLayout()
        days_label = QLabel("Количество дней:")
        days_label.setFont(QFont("Segoe UI", 14))  # Увеличенный шрифт
        days_layout.addWidget(days_label)
        self.days_spinbox = QSpinBox()
        self.days_spinbox.setRange(1, 3650)  # от 1 дня до 10 лет
        self.days_spinbox.setValue(30)
        self.days_spinbox.setFont(QFont("Segoe UI", 14))  # Увеличенный шрифт
        days_layout.addWidget(self.days_spinbox)
        days_layout.addStretch()
        params_layout.addLayout(days_layout)

        # Аппаратный ID
        hw_id_layout = QHBoxLayout()
        hw_id_label = QLabel("ID оборудования:")
        hw_id_label.setFont(QFont("Segoe UI", 14))  # Увеличенный шрифт
        hw_id_layout.addWidget(hw_id_label)
        self.hw_id_edit = QLineEdit()
        self.hw_id_edit.setText(current_hardware_id)
        self.hw_id_edit.setFont(QFont("Consolas", 14))  # Увеличенный шрифт
        self.hw_id_edit.setPlaceholderText("Введите 8-символьный ID оборудования")
        hw_id_layout.addWidget(self.hw_id_edit)
        params_layout.addLayout(hw_id_layout)

        # Чекбокс для использования текущего hardware_id
        self.use_current_hardware = QCheckBox("Использовать ID текущего оборудования")
        self.use_current_hardware.setFont(QFont("Segoe UI", 14))  # Увеличенный шрифт
        self.use_current_hardware.setChecked(True)
        self.use_current_hardware.toggled.connect(self.on_use_current_hardware_toggled)
        params_layout.addWidget(self.use_current_hardware)

        layout.addWidget(params_group)

        # Кнопки генерации
        buttons_layout = QHBoxLayout()

        generate_btn = QPushButton("Сгенерировать ключ")
        generate_btn.setFont(QFont("Segoe UI", 14))  # Увеличенный шрифт
        generate_btn.clicked.connect(self.generate_license)
        generate_btn.setStyleSheet("QPushButton { padding: 15px; background-color: #4CAF50; color: white; }")
        buttons_layout.addWidget(generate_btn)

        test_btn = QPushButton("Проверить ключ")
        test_btn.setFont(QFont("Segoe UI", 14))  # Увеличенный шрифт
        test_btn.clicked.connect(self.test_license)
        test_btn.setStyleSheet("QPushButton { padding: 15px; background-color: #2196F3; color: white; }")
        buttons_layout.addWidget(test_btn)

        clear_btn = QPushButton("Очистить")
        clear_btn.setFont(QFont("Segoe UI", 14))  # Увеличенный шрифт
        clear_btn.clicked.connect(self.clear_output)
        clear_btn.setStyleSheet("QPushButton { padding: 15px; }")
        buttons_layout.addWidget(clear_btn)

        layout.addLayout(buttons_layout)

        # Поле вывода
        output_group = QGroupBox("Сгенерированный ключ и информация")
        output_group.setFont(QFont("Segoe UI", 14))  # Увеличенный шрифт
        output_layout = QVBoxLayout(output_group)

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setFont(QFont("Consolas", 14))  # Увеличенный шрифт
        output_layout.addWidget(self.output_text)

        layout.addWidget(output_group)

        # Кнопка копирования
        copy_btn = QPushButton("Скопировать ключ в буфер обмена")
        copy_btn.setFont(QFont("Segoe UI", 14))  # Увеличенный шрифт
        copy_btn.clicked.connect(self.copy_to_clipboard)
        copy_btn.setStyleSheet("QPushButton { padding: 12px; background-color: #FF9800; color: white; }")
        layout.addWidget(copy_btn)

    def on_use_current_hardware_toggled(self, checked):
        """Обработчик переключения чекбокса использования текущего hardware_id"""
        if checked:
            # Использовать текущий hardware_id
            current_id = self.license_manager.get_hardware_id()
            self.hw_id_edit.setText(current_id)
            self.hw_id_edit.setEnabled(False)
        else:
            # Разрешить ввод произвольного hardware_id
            self.hw_id_edit.setEnabled(True)
            self.hw_id_edit.setFocus()

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
            license_key = self.license_manager.generate_license_key(days, hardware_id)

            # Проверяем ключ
            is_valid, validation_result = self.license_manager.validate_license_key(license_key)

            output = f"""ЛИЦЕНЗИОННЫЙ КЛЮЧ УСПЕШНО СОЗДАН
{'=' * 50}

📋 Ключ: 
{license_key}

📅 Срок действия: {days} дней
🖥️  ID оборудования: {hardware_id}
✅ Статус проверки: {'Валиден' if is_valid else 'Невалиден'}

{'=' * 50}
ИНСТРУКЦИЯ ДЛЯ ПОЛЬЗОВАТЕЛЯ:

1. Запустите программу
2. Перейдите в раздел "Настройки" → "Лицензия"
3. Введите ключ в поле "Лицензионный ключ"
4. Нажмите кнопку "Активировать"

⚠️  ВНИМАНИЕ:
• Ключ будет действителен только на оборудовании с ID: {hardware_id}
• Для активации на другом компьютере потребуется новый ключ
• Срок действия: с момента активации
"""
            self.output_text.setPlainText(output)

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сгенерировать ключ: {str(e)}")

    def test_license(self):
        """Проверить существующий ключ"""
        key, ok = QInputDialog.getText(self, 'Проверка ключа', 'Введите лицензионный ключ для проверки:')
        if ok and key:
            try:
                is_valid, result = self.license_manager.validate_license_key(key.strip())
                if is_valid:
                    expiration_date = result['expiration_date'][:10]  # Берем только дату
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
            # Извлекаем только ключ из текста
            lines = text.split('\n')
            for line in lines:
                if line.startswith('DF-'):
                    key = line.strip()
                    clipboard = QApplication.clipboard()
                    clipboard.setText(key)
                    QMessageBox.information(self, "Успех", "Ключ скопирован в буфер обмена")
                    return

            # Если не нашли ключ в формате DF-..., ищем после "Ключ:"
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

    # Устанавливаем стиль приложения
    app.setStyle('Fusion')
    app.setFont(QFont("Segoe UI", 14))  # Увеличенный шрифт по умолчанию для всего приложения

    generator = LicenseGenerator()
    generator.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()