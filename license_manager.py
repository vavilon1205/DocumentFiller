# license_manager.py - управление лицензиями (исправленная версия)
import json
import os
import hashlib
import platform
import uuid
from datetime import datetime, timedelta


class LicenseManager:
    def __init__(self, script_dir):
        self.script_dir = script_dir
        self.license_path = os.path.join(script_dir, "license.json")

        # Секретный ключ для генерации и проверки лицензий
        self.secret_key = "document_filler_secret_2024"

        # Загружаем или создаем лицензию
        self.license_data = self.load_or_create_license()

    def load_or_create_license(self):
        """Загрузить существующую лицензию или создать trial при первом запуске"""
        try:
            # Пытаемся загрузить существующую лицензию
            if os.path.exists(self.license_path):
                with open(self.license_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Проверяем оборудование
                if data.get('hardware_id') != self.get_hardware_id():
                    print("Обнаружено изменение оборудования, создаем новую trial лицензию")
                    return self.create_trial_license()

                return data
            else:
                # Файл лицензии не существует - создаем trial
                print("Лицензия не найдена, создаем trial лицензию")
                return self.create_trial_license()

        except Exception as e:
            print(f"Ошибка загрузки лицензии: {e}, создаем trial лицензию")
            return self.create_trial_license()

    def create_trial_license(self):
        """Создать trial лицензию на 7 дней"""
        # Устанавливаем expiration_date на конец дня (23:59:59)
        expiration_date = datetime.now().replace(hour=23, minute=59, second=59, microsecond=0) + timedelta(days=7)

        trial_data = {
            "activated": True,  # Trial считается активированным
            "license_key": "TRIAL_VERSION",
            "activation_date": datetime.now().isoformat(),
            "expiration_date": expiration_date.isoformat(),
            "type": "trial",
            "features": ["basic"],
            "hardware_id": self.get_hardware_id(),
            "is_trial": True
        }

        self.save_license(trial_data)
        return trial_data

    def save_license(self, data=None):
        """Сохранить данные лицензии"""
        if data is None:
            data = self.license_data

        try:
            with open(self.license_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self.license_data = data
            return True
        except Exception as e:
            print(f"Ошибка сохранения лицензии: {e}")
            return False

    def get_hardware_id(self):
        """Получить идентификатор оборудования"""
        try:
            # Используем комбинацию hostname и MAC-адреса
            system_info = platform.node()  # Hostname

            # MAC-адрес
            try:
                mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff)
                                for elements in range(0, 8 * 6, 8)][::-1])
                system_info += mac
            except:
                pass

            # Создаем хеш
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

    def generate_license_key(self, days=30, hardware_id=None):
        """Сгенерировать лицензионный ключ"""
        if hardware_id is None:
            hardware_id = self.get_hardware_id()

        # Устанавливаем expiration_date на конец дня (23:59:59)
        expiration_date = datetime.now().replace(hour=23, minute=59, second=59, microsecond=0) + timedelta(days=days)

        # Форматируем дату для ключа
        date_str = expiration_date.strftime('%Y%m%d')

        # Форматируем дни для ключа
        days_str = f"{days:03d}"

        # Создаем строку для подписи
        data_string = f"{hardware_id}{date_str}{days_str}{self.secret_key}"

        # Создаем подпись
        signature = hashlib.sha256(data_string.encode()).hexdigest()[:16].upper()

        # Формируем ключ
        license_key = f"DF-{hardware_id}-{date_str}-{days_str}-{signature}"

        return license_key

    def validate_license_key(self, license_key):
        """Проверить валидность лицензионного ключа"""
        try:
            # Проверяем формат ключа
            if not license_key.startswith("DF-"):
                return False, "Неверный формат лицензионного ключа"

            parts = license_key.split("-")
            if len(parts) != 5:
                return False, "Неверный формат лицензионного ключа"

            hardware_id_part = parts[1]
            date_str = parts[2]
            days_str = parts[3]
            signature = parts[4]

            # Проверяем дату
            try:
                expiration_date = datetime.strptime(date_str, "%Y%m%d").replace(hour=23, minute=59, second=59,
                                                                                microsecond=0)
            except ValueError:
                return False, "Неверный формат даты в лицензионном ключе"

            # Проверяем количество дней
            try:
                days = int(days_str)
            except ValueError:
                return False, "Неверный формат количества дней"

            # Проверяем, не истекла ли лицензия
            if datetime.now() > expiration_date:
                return False, "Срок действия лицензии истек"

            # Проверяем оборудование
            current_hardware_id = self.get_hardware_id()
            if hardware_id_part != current_hardware_id:
                return False, f"Лицензионный ключ не подходит для этого компьютера. Ожидался ID: {current_hardware_id}, получен: {hardware_id_part}"

            # Проверяем подпись
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

    def activate_license(self, license_key):
        """Активировать лицензию"""
        try:
            # Проверяем ключ
            is_valid, result = self.validate_license_key(license_key)

            if not is_valid:
                return False, result

            license_info = result

            # Активируем лицензию
            self.license_data.update({
                "activated": True,
                "license_key": license_key,
                "activation_date": datetime.now().isoformat(),
                "expiration_date": license_info['expiration_date'],
                "type": license_info['type'],
                "features": ["basic", "premium"],
                "hardware_id": self.get_hardware_id(),
                "is_trial": False  # Сбрасываем trial статус
            })

            self.save_license()
            return True, f"Лицензия успешно активирована на {license_info['days']} дней"

        except Exception as e:
            return False, f"Ошибка активации лицензии: {str(e)}"

    def check_license(self):
        """Проверить статус лицензии - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        # Проверяем trial лицензию
        if self.license_data.get('is_trial', False):
            return self.check_trial_license()

        # Проверяем обычную лицензию
        if not self.license_data.get('activated', False):
            return False, 0, "Лицензия не активирована"

        expiration_date_str = self.license_data.get('expiration_date')
        if not expiration_date_str:
            return False, 0, "Ошибка лицензии: отсутствует дата окончания"

        try:
            expiration_date = datetime.fromisoformat(expiration_date_str)

            # Строгая проверка оборудования
            if self.license_data.get('hardware_id') != self.get_hardware_id():
                return False, 0, "Лицензия не действительна для этого компьютера"

            if datetime.now() > expiration_date:
                return False, 0, "Срок действия лицензии истек"

            # ИСПРАВЛЕНИЕ: Правильно вычисляем количество оставшихся дней
            time_difference = expiration_date - datetime.now()
            days_left = time_difference.days

            # Если осталось меньше дня, но лицензия еще действительна, показываем 1 день
            if days_left == 0 and time_difference.total_seconds() > 0:
                days_left = 1

            return True, days_left, "Лицензия активна"

        except Exception as e:
            return False, 0, f"Ошибка проверки лицензии: {str(e)}"

    def check_trial_license(self):
        """Проверить trial лицензию - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        expiration_date_str = self.license_data.get('expiration_date')
        if not expiration_date_str:
            # Создаем trial лицензию на 7 дней
            return self.create_short_trial()

        try:
            expiration_date = datetime.fromisoformat(expiration_date_str)

            if datetime.now() > expiration_date:
                return False, 0, "Пробный период истек. Требуется активация лицензии."

            # ИСПРАВЛЕНИЕ: Правильно вычисляем количество оставшихся дней
            time_difference = expiration_date - datetime.now()
            days_left = time_difference.days

            # Если осталось меньше дня, но лицензия еще действительна, показываем 1 день
            if days_left == 0 and time_difference.total_seconds() > 0:
                days_left = 1

            return True, days_left, f"Пробный период активен, осталось {days_left} дней"

        except Exception as e:
            return False, 0, f"Ошибка пробной лицензии: {str(e)}"

    def create_short_trial(self):
        """Создать короткий trial период (7 дней) при проблемах с лицензией"""
        # Устанавливаем expiration_date на конец дня (23:59:59)
        expiration_date = datetime.now().replace(hour=23, minute=59, second=59, microsecond=0) + timedelta(days=7)

        trial_data = {
            "activated": True,
            "license_key": "TRIAL_VERSION",
            "activation_date": datetime.now().isoformat(),
            "expiration_date": expiration_date.isoformat(),
            "type": "trial",
            "features": ["basic"],
            "hardware_id": self.get_hardware_id(),
            "is_trial": True
        }

        self.save_license(trial_data)
        days_left = 7
        return True, days_left, f"Создан пробный период на {days_left} дней"

    def is_feature_available(self, feature):
        """Проверить доступность функции"""
        is_valid, _, _ = self.check_license()
        if not is_valid:
            return False

        features = self.license_data.get('features', ['basic'])
        return feature in features

    def get_license_info(self):
        """Получить информацию о лицензии"""
        is_valid, days_left, message = self.check_license()

        return {
            "is_valid": is_valid,
            "days_left": days_left,
            "message": message,
            "type": self.license_data.get('type', 'trial'),
            "activated": self.license_data.get('activated', False),
            "is_trial": self.license_data.get('is_trial', True),
            "expiration_date": self.license_data.get('expiration_date'),
            "features": self.license_data.get('features', [])
        }