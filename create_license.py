# license_generator.py - графический генератор лицензионных ключей
import sys
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QTextEdit, QSpinBox,
                             QGroupBox, QMessageBox, QWidget, QCheckBox)
from PyQt5.QtCore import Qt
from license_manager import LicenseManager


class LicenseGenerator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.license_manager = LicenseManager(os.path.dirname(os.path.abspath(__file__)))
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Генератор лицензионных ключей")
        self.setGeometry(300, 300, 600, 500)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        # Информация о системе
        info_group = QGroupBox("Информация о системе")
        info_layout = QVBoxLayout(info_group)

        self.hardware_id_label = QLabel()
        self.update_hardware_id()
        info_layout.addWidget(self.hardware_id_label)

        layout.addWidget(info_group)

        # Параметры лицензии
        params_group = QGroupBox("Параметры лицензии")
        params_layout = QVBoxLayout(params_group)

        # Количество дней
        days_layout = QHBoxLayout()
        days_layout.addWidget(QLabel("Количество дней:"))
        self.days_spinbox = QSpinBox()
        self.days_spinbox.setRange(1, 3650)  # от 1 дня до 10 лет
        self.days_spinbox.setValue(30)
        days_layout.addWidget(self.days_spinbox)
        days_layout.addStretch()
        params_layout.addLayout(days_layout)

        # Аппаратный ID
        hw_id_layout = QHBoxLayout()
        hw_id_layout.addWidget(QLabel("ID оборудования:"))
        self.hw_id_edit = QLineEdit()
        self.hw_id_edit.setText(self.license_manager.get_hardware_id())
        hw_id_layout.addWidget(self.hw_id_edit)
        params_layout.addLayout(hw_id_layout)

        # Чекбокс для использования текущего hardware_id
        self.use_current_hardware = QCheckBox("Использовать текущий ID оборудования")
        self.use_current_hardware.setChecked(True)
        self.use_current_hardware.toggled.connect(self.on_use_current_hardware_toggled)
        params_layout.addWidget(self.use_current_hardware)

        layout.addWidget(params_group)

        # Кнопки генерации
        buttons_layout = QHBoxLayout()

        generate_btn = QPushButton("Сгенерировать ключ")
        generate_btn.clicked.connect(self.generate_license)
        generate_btn.setStyleSheet("QPushButton { font-size: 12pt; padding: 10px; }")
        buttons_layout.addWidget(generate_btn)

        clear_btn = QPushButton("Очистить")
        clear_btn.clicked.connect(self.clear_output)
        buttons_layout.addWidget(clear_btn)

        layout.addLayout(buttons_layout)

        # Поле вывода
        output_group = QGroupBox("Сгенерированный ключ")
        output_layout = QVBoxLayout(output_group)

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        output_layout.addWidget(self.output_text)

        layout.addWidget(output_group)

        # Кнопка копирования
        copy_btn = QPushButton("Скопировать ключ в буфер обмена")
        copy_btn.clicked.connect(self.copy_to_clipboard)
        layout.addWidget(copy_btn)

    def update_hardware_id(self):
        """Обновить отображение hardware_id"""
        hardware_id = self.license_manager.get_hardware_id()
        self.hardware_id_label.setText(f"ID текущего оборудования: {hardware_id}")

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

    def generate_license(self):
        try:
            days = self.days_spinbox.value()
            if self.use_current_hardware.isChecked():
                hardware_id = self.license_manager.get_hardware_id()
            else:
                hardware_id = self.hw_id_edit.text().strip()
                if not hardware_id:
                    QMessageBox.warning(self, "Ошибка", "Введите ID оборудования")
                    return

            license_key = self.license_manager.generate_license_key(days, hardware_id)

            output = f"""ЛИЦЕНЗИОННЫЙ КЛЮЧ УСПЕШНО СОЗДАН

Ключ: {license_key}
Срок действия: {days} дней
ID оборудования: {hardware_id}

Инструкция для пользователя:
1. Запустите программу
2. Перейдите в раздел "Настройки" -> "Лицензия"
3. Введите ключ в поле "Лицензионный ключ"
4. Нажмите кнопку "Активировать"

Ключ будет действителен только на указанном оборудовании.
"""
            self.output_text.setPlainText(output)

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сгенерировать ключ: {str(e)}")

    def clear_output(self):
        self.output_text.clear()

    def copy_to_clipboard(self):
        text = self.output_text.toPlainText()
        if text:
            # Извлекаем только ключ из текста
            lines = text.split('\n')
            for line in lines:
                if line.startswith('Ключ: '):
                    key = line.replace('Ключ: ', '').strip()
                    clipboard = QApplication.clipboard()
                    clipboard.setText(key)
                    QMessageBox.information(self, "Успех", "Ключ скопирован в буфер обмена")
                    return
            QMessageBox.warning(self, "Внимание", "Не удалось найти ключ для копирования")


def main():
    app = QApplication(sys.argv)
    generator = LicenseGenerator()
    generator.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()