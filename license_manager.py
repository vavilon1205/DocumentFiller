# license_manager.py - управление лицензиями с авто-загрузкой настроек из repo_config.json
import json
import os
import hashlib
import platform
import uuid
import requests
from datetime import datetime, timedelta


class LicenseManager:
    def __init__(self, script_dir):
        self.script_dir = script_dir
        self.license_path = os.path.join(script_dir, "license.json")
        self.trial_marker_path = os.path.join(script_dir, ".trial_used")

        # Загружаем настройки из repo_config.json
        self.repo_config = self.load_repo_config()

        # URL онлайн-базы лицензий из repo_config.json
        self.online_db_url = self.repo_config.get("online_license_db_url", "")

        # Секретный ключ
        self.secret_key = "document_filler_secret_2024"

        # Загружаем или создаем лицензию
        self.license_data = self.load_or_create_license()

    def load_repo_config(self):
        """Загрузить настройки из repo_config.json"""
        try:
            config_path = os.path.join(self.script_dir, "repo_config.json")
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                # Создаем конфиг по умолчанию
                default_config = {
                    "type": "yandex_disk",
                    "yandex_disk_url": "",
                    "current_version": "1.0.0",
                    "online_license_db_url": ""
                }
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, indent=2, ensure_ascii=False)
                return default_config
        except Exception as e:
            print(f"Ошибка загрузки repo_config.json: {e}")
            return {}

    def load_or_create_license(self):
        """Загрузить существующую лицензию или создать trial"""
        try:
            # Пытаемся загрузить существующую лицензию
            if os.path.exists(self.license_path):
                with open(self.license_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Проверяем оборудование
                if data.get('hardware_id') != self.get_hardware_id():
                    print("Обнаружено изменение оборудования")
                    return self.create_trial_license()

                return data
            else:
                # Файл лицензии не существует
                if self.was_trial_used():
                    print("Пробный период уже был использован ранее")
                    return self.create_expired_license()
                else:
                    print("Создаем trial лицензию")
                    return self.create_trial_license()

        except Exception as e:
            print(f"Ошибка загрузки лицензии: {e}")
            return self.create_trial_license()

    def was_trial_used(self):
        """Проверить, был ли уже использован пробный период"""
        # Проверяем маркер использования trial
        if os.path.exists(self.trial_marker_path):
            return True

        # Также проверяем наличие любой существующей лицензии в системе
        try:
            # Проверяем в реестре Windows (если Windows)
            if platform.system() == "Windows":
                try:
                    import winreg
                    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Software\\DocumentFiller")
                    winreg.QueryValueEx(key, "TrialUsed")
                    winreg.CloseKey(key)
                    return True
                except:
                    pass

            # Проверяем в других возможных местах
            possible_locations = [
                os.path.join(os.environ.get('APPDATA', ''), "DocumentFiller", ".trial_used"),
                os.path.join(os.environ.get('LOCALAPPDATA', ''), "DocumentFiller", ".trial_used"),
                os.path.expanduser("~/.documentfiller_trial_used"),
            ]

            for location in possible_locations:
                if os.path.exists(location):
                    return True

        except Exception as e:
            print(f"Ошибка проверки истории trial: {e}")

        return False

    def mark_trial_used(self):
        """Пометить пробный период как использованный"""
        try:
            # Создаем файл-маркер
            with open(self.trial_marker_path, 'w') as f:
                f.write("trial_used")

            # Дополнительно сохраняем в реестр (если Windows)
            if platform.system() == "Windows":
                try:
                    import winreg
                    key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, "Software\\DocumentFiller")
                    winreg.SetValueEx(key, "TrialUsed", 0, winreg.REG_SZ, "1")
                    winreg.CloseKey(key)
                except Exception as e:
                    print(f"Не удалось сохранить в реестр: {e}")

            # Сохраняем в другие места
            other_locations = [
                os.path.join(os.environ.get('APPDATA', ''), "DocumentFiller"),
                os.path.join(os.environ.get('LOCALAPPDATA', ''), "DocumentFiller"),
                os.path.expanduser("~"),
            ]

            for location in other_locations:
                try:
                    os.makedirs(location, exist_ok=True)
                    marker_path = os.path.join(location, ".trial_used")
                    with open(marker_path, 'w') as f:
                        f.write("trial_used")
                except Exception as e:
                    print(f"Не удалось создать маркер в {location}: {e}")

        except Exception as e:
            print(f"Ошибка создания маркера trial: {e}")

    def create_trial_license(self):
        """Создать trial лицензию на 7 дней"""
        # Помечаем trial как использованный
        self.mark_trial_used()

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
        return trial_data

    def create_expired_license(self):
        """Создать истекшую лицензию"""
        expired_date = datetime.now().replace(hour=23, minute=59, second=59, microsecond=0) - timedelta(days=1)

        expired_data = {
            "activated": False,
            "license_key": "EXPIRED",
            "activation_date": expired_date.isoformat(),
            "expiration_date": expired_date.isoformat(),
            "type": "expired",
            "features": [],
            "hardware_id": self.get_hardware_id(),
            "is_trial": False
        }

        self.save_license(expired_data)
        return expired_data

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

    def check_online_license(self):
        """Проверить лицензию в онлайн-базе"""
        if not self.online_db_url:
            return False, "URL онлайн-базы не настроен"

        try:
            # Пытаемся скачать онлайн-базу
            response = requests.get(self.online_db_url, timeout=10)
            if response.status_code == 200:
                online_db = response.json()
                users = online_db.get("users", [])

                # Ищем нашу лицензию по hardware_id
                hardware_id = self.get_hardware_id()
                for user in users:
                    if user.get("hardware_id") == hardware_id and user.get("active", True):
                        # Проверяем срок действия
                        expires = user.get("expires")
                        if expires:
                            try:
                                expire_date = datetime.fromisoformat(expires.replace('Z', '+00:00'))
                                if datetime.now() > expire_date:
                                    return False, "Срок действия лицензии истек"
                            except:
                                pass

                        # Лицензия действительна - обновляем локальные данные
                        self.license_data.update({
                            "activated": True,
                            "license_key": "ONLINE_VALID",
                            "activation_date": datetime.now().isoformat(),
                            "expiration_date": expires or "",
                            "type": user.get("license_type", "premium"),
                            "features": ["basic", "premium"],
                            "hardware_id": hardware_id,
                            "is_trial": False,
                            "online_valid": True,
                            "last_online_check": datetime.now().isoformat(),
                            "user_info": {
                                "name": user.get("name"),
                                "email": user.get("email"),
                                "phone": user.get("phone")
                            }
                        })

                        self.save_license()
                        return True, "Онлайн-лицензия активна"

                return False, "Лицензия не найдена в онлайн-базе"
            else:
                return False, f"Ошибка доступа к онлайн-базе: {response.status_code}"

        except Exception as e:
            return False, f"Ошибка онлайн-проверки: {str(e)}"

    def check_license(self):
        """Проверить лицензию (сначала онлайн, потом оффлайн)"""
        # Сначала пробуем онлайн-проверку
        online_success, online_message = self.check_online_license()

        if online_success:
            # Онлайн-лицензия действительна
            print("Лицензия проверена онлайн")

            # Вычисляем оставшиеся дни
            expires = self.license_data.get("expiration_date")
            if expires:
                try:
                    expire_date = datetime.fromisoformat(expires.replace('Z', '+00:00'))
                    days_left = (expire_date - datetime.now()).days
                    if days_left < 0:
                        days_left = 0
                except:
                    days_left = 999  # Бессрочная
            else:
                days_left = 999  # Бессрочная

            return True, days_left, online_message

        else:
            # Онлайн-проверка не удалась, используем оффлайн
            print(f"Онлайн-проверка не удалась: {online_message}")
            return self.check_offline_license()

    def check_offline_license(self):
        """Проверить оффлайн-лицензию"""
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

            # Проверка оборудования
            if self.license_data.get('hardware_id') != self.get_hardware_id():
                return False, 0, "Лицензия не действительна для этого компьютера"

            if datetime.now() > expiration_date:
                return False, 0, "Срок действия лицензии истек"

            # Вычисляем оставшиеся дни
            time_difference = expiration_date - datetime.now()
            days_left = time_difference.days

            if days_left == 0 and time_difference.total_seconds() > 0:
                days_left = 1

            return True, days_left, "Оффлайн-лицензия активна"

        except Exception as e:
            return False, 0, f"Ошибка проверки лицензии: {str(e)}"

    def check_trial_license(self):
        """Проверить trial лицензию"""
        expiration_date_str = self.license_data.get('expiration_date')
        if not expiration_date_str:
            # Создаем trial лицензию на 7 дней
            return self.create_short_trial()

        try:
            expiration_date = datetime.fromisoformat(expiration_date_str)

            if datetime.now() > expiration_date:
                return False, 0, "Пробный период истек. Требуется активация лицензии."

            # Вычисляем оставшиеся дни
            time_difference = expiration_date - datetime.now()
            days_left = time_difference.days

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

    def generate_license_key(self, days=30, hardware_id=None):
        """Сгенерировать лицензионный ключ (для обратной совместимости)"""
        if hardware_id is None:
            hardware_id = self.get_hardware_id()

        expiration_date = datetime.now().replace(hour=23, minute=59, second=59, microsecond=0) + timedelta(days=days)

        date_str = expiration_date.strftime('%Y%m%d')
        days_str = f"{days:03d}"

        data_string = f"{hardware_id}{date_str}{days_str}{self.secret_key}"
        signature = hashlib.sha256(data_string.encode()).hexdigest()[:16].upper()

        license_key = f"DF-{hardware_id}-{date_str}-{days_str}-{signature}"
        return license_key

    def validate_license_key(self, license_key):
        """Проверить валидность лицензионного ключа (для обратной совместимости)"""
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
                expiration_date = datetime.strptime(date_str, "%Y%m%d").replace(hour=23, minute=59, second=59,
                                                                                microsecond=0)
            except ValueError:
                return False, "Неверный формат даты в лицензионном ключе"

            try:
                days = int(days_str)
            except ValueError:
                return False, "Неверный формат количества дней"

            if datetime.now() > expiration_date:
                return False, "Срок действия лицензии истек"

            current_hardware_id = self.get_hardware_id()
            if hardware_id_part != current_hardware_id:
                return False, f"Лицензионный ключ не подходит для этого компьютера. Ожидался ID: {current_hardware_id}, получен: {hardware_id_part}"

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
        """Активировать лицензию (для обратной совместимости)"""
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
                "is_trial": False
            })

            self.save_license()
            return True, f"Лицензия успешно активирована на {license_info['days']} дней"

        except Exception as e:
            return False, f"Ошибка активации лицензии: {str(e)}"

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
            "online_valid": self.license_data.get('online_valid', False),
            "expiration_date": self.license_data.get('expiration_date'),
            "last_online_check": self.license_data.get('last_online_check'),
            "user_info": self.license_data.get('user_info', {}),
            "features": self.license_data.get('features', []),
            "hardware_id": self.get_hardware_id()
        }