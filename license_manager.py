# license_manager.py - управление лицензиями с защитой от изменений
import json
import os
import hashlib
import hmac  # Добавлен импорт модуля hmac
import platform
import uuid
import requests
from datetime import datetime, timedelta
import sys
import sqlite3
import winreg  # Только для Windows


class LicenseManager:
    def __init__(self, script_dir):
        self.script_dir = script_dir
        self.license_path = os.path.join(script_dir, "license.db")
        self.trial_marker_path = os.path.join(script_dir, ".trial_used")

        # Секретные ключи для шифрования/проверки
        self.secret_key = "document_filler_secret_2024"
        self.hmac_key = b"license_hmac_protection_key_32"

        # Инициализация базы данных
        self.init_database()

        # Загружаем настройки из repo_config.json
        self.repo_config = self.load_repo_config()

        # URL онлайн-базы лицензий из repo_config.json
        self.online_db_url = self.repo_config.get("online_license_db_url", "")

        # Загружаем или создаем лицензию
        self.license_data = self.load_or_create_license()

    def init_database(self):
        """Инициализировать базу данных для хранения лицензии"""
        try:
            conn = sqlite3.connect(self.license_path)
            cursor = conn.cursor()

            # Создаем таблицу лицензий
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS licenses (
                    id INTEGER PRIMARY KEY,
                    hardware_id TEXT NOT NULL,
                    license_key TEXT NOT NULL,
                    activation_date TEXT,
                    expiration_date TEXT,
                    license_type TEXT,
                    features TEXT,
                    is_trial INTEGER DEFAULT 0,
                    is_activated INTEGER DEFAULT 0,
                    checksum TEXT,
                    created_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(hardware_id)
                )
            ''')

            # Создаем таблицу для отслеживания изменений
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS license_log (
                    id INTEGER PRIMARY KEY,
                    license_id INTEGER,
                    action TEXT,
                    details TEXT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (license_id) REFERENCES licenses (id)
                )
            ''')

            conn.commit()
            conn.close()

        except Exception as e:
            print(f"Ошибка инициализации базы данных: {e}")
            # Создаем резервный файл в случае ошибки
            self.create_backup_license_file()

    def create_backup_license_file(self):
        """Создать резервный файл лицензии в случае проблем с БД"""
        backup_path = os.path.join(self.script_dir, "license_backup.json")
        try:
            default_license = {
                "activated": False,
                "license_key": "",
                "hardware_id": self.get_hardware_id(),
                "type": "none",
                "features": [],
                "is_trial": False,
                "is_protected": True,
                "checksum": self.generate_checksum("")
            }
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(default_license, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Ошибка создания резервного файла: {e}")

    def generate_checksum(self, data):
        """Создать контрольную сумму для проверки целостности"""
        if isinstance(data, dict):
            data_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
        else:
            data_str = str(data)

        # Используем HMAC для создания защищенной контрольной суммы
        hmac_obj = hmac.new(self.hmac_key, data_str.encode('utf-8'), hashlib.sha256)
        return hmac_obj.hexdigest()

    def verify_checksum(self, data, checksum):
        """Проверить контрольную сумму"""
        expected_checksum = self.generate_checksum(data)
        return hmac.compare_digest(expected_checksum, checksum)

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
            # Пытаемся загрузить из базы данных
            license_data = self.load_license_from_db()

            if license_data:
                # Проверяем оборудование
                if license_data.get('hardware_id') != self.get_hardware_id():
                    print("Обнаружено изменение оборудования")
                    self.log_license_action("hardware_mismatch",
                                            f"Ожидалось: {license_data.get('hardware_id')}, Получено: {self.get_hardware_id()}")
                    return self.create_trial_license()

                # Проверяем целостность данных
                if not self.verify_license_integrity(license_data):
                    print("Обнаружено нарушение целостности лицензии")
                    self.log_license_action("integrity_violation", "Контрольная сумма не совпадает")
                    return self.create_trial_license()

                return license_data
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

    def load_license_from_db(self):
        """Загрузить лицензию из базы данных"""
        try:
            conn = sqlite3.connect(self.license_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT hardware_id, license_key, activation_date, expiration_date, 
                       license_type, features, is_trial, is_activated, checksum
                FROM licenses 
                WHERE hardware_id = ?
                ORDER BY id DESC
                LIMIT 1
            ''', (self.get_hardware_id(),))

            row = cursor.fetchone()
            conn.close()

            if row:
                # Разбираем features из строки JSON
                try:
                    features = json.loads(row[5]) if row[5] else []
                except:
                    features = []

                license_data = {
                    "hardware_id": row[0],
                    "license_key": row[1],
                    "activation_date": row[2],
                    "expiration_date": row[3],
                    "type": row[4],
                    "features": features,
                    "is_trial": bool(row[6]),
                    "activated": bool(row[7]),
                    "checksum": row[8]
                }
                return license_data

            return None

        except Exception as e:
            print(f"Ошибка загрузки лицензии из БД: {e}")
            return None

    def save_license_to_db(self, license_data):
        """Сохранить лицензию в базу данных"""
        try:
            # Генерируем контрольную сумму
            data_to_hash = {k: v for k, v in license_data.items() if k != 'checksum'}
            checksum = self.generate_checksum(data_to_hash)

            conn = sqlite3.connect(self.license_path)
            cursor = conn.cursor()

            # Проверяем существующую запись
            cursor.execute('SELECT id FROM licenses WHERE hardware_id = ?',
                           (license_data.get('hardware_id'),))

            if cursor.fetchone():
                # Обновляем существующую запись
                cursor.execute('''
                    UPDATE licenses 
                    SET license_key = ?, activation_date = ?, expiration_date = ?,
                        license_type = ?, features = ?, is_trial = ?, is_activated = ?, checksum = ?
                    WHERE hardware_id = ?
                ''', (
                    license_data.get('license_key', ''),
                    license_data.get('activation_date'),
                    license_data.get('expiration_date'),
                    license_data.get('type', 'trial'),
                    json.dumps(license_data.get('features', [])),
                    1 if license_data.get('is_trial', False) else 0,
                    1 if license_data.get('activated', False) else 0,
                    checksum,
                    license_data.get('hardware_id')
                ))
            else:
                # Создаем новую запись
                cursor.execute('''
                    INSERT INTO licenses 
                    (hardware_id, license_key, activation_date, expiration_date, 
                     license_type, features, is_trial, is_activated, checksum)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    license_data.get('hardware_id'),
                    license_data.get('license_key', ''),
                    license_data.get('activation_date'),
                    license_data.get('expiration_date'),
                    license_data.get('type', 'trial'),
                    json.dumps(license_data.get('features', [])),
                    1 if license_data.get('is_trial', False) else 0,
                    1 if license_data.get('activated', False) else 0,
                    checksum
                ))

            # Логируем действие
            license_id = cursor.lastrowid
            self.log_license_action_db(cursor, license_id, "save",
                                       f"Сохранена лицензия типа: {license_data.get('type')}")

            conn.commit()
            conn.close()

            return True

        except Exception as e:
            print(f"Ошибка сохранения лицензии в БД: {e}")
            return False

    def log_license_action_db(self, cursor, license_id, action, details):
        """Записать действие с лицензией в лог"""
        try:
            cursor.execute('''
                INSERT INTO license_log (license_id, action, details)
                VALUES (?, ?, ?)
            ''', (license_id, action, details))
        except Exception as e:
            print(f"Ошибка записи в лог: {e}")

    def log_license_action(self, action, details):
        """Записать действие с лицензией (для обратной совместимости)"""
        try:
            log_path = os.path.join(self.script_dir, "license_actions.log")
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(f"{datetime.now().isoformat()}: {action} - {details}\n")
        except Exception as e:
            print(f"Ошибка записи в лог действий: {e}")

    def verify_license_integrity(self, license_data):
        """Проверить целостность данных лицензии"""
        try:
            if 'checksum' not in license_data:
                return False

            stored_checksum = license_data['checksum']
            data_to_verify = {k: v for k, v in license_data.items() if k != 'checksum'}

            return self.verify_checksum(data_to_verify, stored_checksum)

        except Exception as e:
            print(f"Ошибка проверки целостности: {e}")
            return False

    def was_trial_used(self):
        """Проверить, был ли уже использован пробный период"""
        # Проверяем в базе данных
        try:
            conn = sqlite3.connect(self.license_path)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM licenses WHERE is_trial = 1')
            count = cursor.fetchone()[0]
            conn.close()

            if count > 0:
                return True

        except Exception as e:
            print(f"Ошибка проверки trial в БД: {e}")

        # Проверяем маркер использования trial
        if os.path.exists(self.trial_marker_path):
            return True

        # Проверяем в реестре Windows (если Windows)
        if platform.system() == "Windows":
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                     "Software\\DocumentFiller",
                                     0, winreg.KEY_READ)
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

        return False

    def mark_trial_used(self):
        """Пометить пробный период как использованный"""
        try:
            # Записываем в базу данных
            conn = sqlite3.connect(self.license_path)
            cursor = conn.cursor()

            # Проверяем, есть ли уже запись
            cursor.execute('SELECT id FROM licenses WHERE hardware_id = ?',
                           (self.get_hardware_id(),))

            if not cursor.fetchone():
                # Создаем запись о trial
                cursor.execute('''
                    INSERT INTO licenses 
                    (hardware_id, license_key, license_type, is_trial, is_activated)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    self.get_hardware_id(),
                    "TRIAL_USED_MARKER",
                    "trial_marker",
                    1, 1
                ))

                # Логируем
                license_id = cursor.lastrowid
                self.log_license_action_db(cursor, license_id, "trial_marked",
                                           "Пробный период помечен как использованный")

            conn.commit()
            conn.close()

            # Дополнительно сохраняем в реестр (если Windows)
            if platform.system() == "Windows":
                try:
                    key = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                           "Software\\DocumentFiller")
                    winreg.SetValueEx(key, "TrialUsed", 0, winreg.REG_SZ, "1")
                    winreg.SetValueEx(key, "TrialMarkedDate", 0, winreg.REG_SZ,
                                      datetime.now().isoformat())
                    winreg.CloseKey(key)
                except Exception as e:
                    print(f"Не удалось сохранить в реестр: {e}")

        except Exception as e:
            print(f"Ошибка создания маркера trial: {e}")

    def create_trial_license(self):
        """Создать trial лицензию на 7 дней"""
        # Помечаем trial как использованный
        self.mark_trial_used()

        # Устанавливаем expiration_date на конец дня (23:59:59)
        expiration_date = datetime.now().replace(hour=23, minute=59,
                                                 second=59, microsecond=0) + timedelta(days=7)

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

        self.save_license_to_db(trial_data)
        return trial_data

    def create_expired_license(self):
        """Создать истекшую лицензию"""
        expired_date = datetime.now().replace(hour=23, minute=59,
                                              second=59, microsecond=0) - timedelta(days=1)

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

        self.save_license_to_db(expired_data)
        return expired_data

    def save_license(self, data=None):
        """Сохранить данные лицензии (для обратной совместимости)"""
        if data is None:
            data = self.license_data
        return self.save_license_to_db(data)

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
        """Проверить оффлайн-лицензию с защитой"""
        # Проверяем целостность данных
        if not self.verify_license_integrity(self.license_data):
            print("⚠️ Нарушение целостности лицензии!")
            return False, 0, "Лицензия повреждена или изменена"

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

            # Вычисляем оставшиеся дней
            time_difference = expiration_date - datetime.now()
            days_left = time_difference.days

            if days_left == 0 and time_difference.total_seconds() > 0:
                days_left = 1

            return True, days_left, "Лицензия активна"

        except Exception as e:
            return False, 0, f"Ошибка проверки лицензии: {str(e)}"

    def check_trial_license(self):
        """Проверить trial лицензию с защитой"""
        expiration_date_str = self.license_data.get('expiration_date')
        if not expiration_date_str:
            # Создаем trial лицензию на 7 дней
            return self.create_short_trial()

        try:
            expiration_date = datetime.fromisoformat(expiration_date_str)

            if datetime.now() > expiration_date:
                return False, 0, "Пробный период истек. Требуется активация лицензии."

            # Вычисляем оставшиеся дней
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

        self.save_license_to_db(trial_data)
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

            current_hardware_id = self.get_hardware_id()
            if hardware_id_part != current_hardware_id:
                return False, f"Лицензионный ключ не подходит для этого компьютера. Ожидался ID: {current_hardware_id}, получен: {hardware_id_part}"

            expected_data_string = f"{hardware_id_part}{date_str}{days_str}{self.secret_key}"
            expected_signature = hashlib.sha256(expected_data_string.encode()).hexdigest()[:16].upper()

            # Используем безопасное сравнение строк
            if not hmac.compare_digest(signature, expected_signature):
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
        """Активировать лицензию с проверкой целостности"""
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

            # Сохраняем с защитой
            success = self.save_license_to_db(self.license_data)
            if success:
                return True, f"Лицензия успешно активирована на {license_info['days']} дней"
            else:
                return False, "Ошибка сохранения лицензии"

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
        """Получить информацию о лицензии с защитой"""
        is_valid, days_left, message = self.check_license()

        # Дополнительная проверка целостности
        integrity_check = self.verify_license_integrity(self.license_data)

        return {
            "is_valid": is_valid and integrity_check,
            "days_left": days_left,
            "message": message + (" (целостность нарушена)" if not integrity_check else ""),
            "type": self.license_data.get('type', 'trial'),
            "activated": self.license_data.get('activated', False),
            "is_trial": self.license_data.get('is_trial', True),
            "expiration_date": self.license_data.get('expiration_date'),
            "features": self.license_data.get('features', []),
            "hardware_id": self.get_hardware_id(),
            "integrity_check": integrity_check,
            "is_protected": True
        }