# update_manager.py - обновление через GitHub API
import requests
import json
import os
import sys
import zipfile
import shutil
import tempfile
from pathlib import Path
from datetime import datetime


class UpdateManager:
    def __init__(self):
        self.script_dir = self.get_script_dir()
        self.config = self.load_config()
        self.current_version = self.get_current_version()

    def get_script_dir(self):
        """Получить директорию скрипта"""
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        else:
            return os.path.dirname(os.path.abspath(__file__))

    def load_config(self):
        """Загрузить конфигурацию"""
        try:
            config_path = os.path.join(self.script_dir, 'repo_config.json')
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Ошибка загрузки конфигурации: {e}")
            return {}

    def get_current_version(self):
        """Получить текущую версию"""
        try:
            version_path = os.path.join(self.script_dir, 'version_config.json')
            with open(version_path, 'r', encoding='utf-8') as f:
                version_data = json.load(f)
                return version_data.get('current_version', '1.0.0')
        except Exception as e:
            print(f"Ошибка получения версии: {e}")
            return '1.0.0'

    def check_for_updates(self):
        """Проверить наличие обновлений через GitHub API"""
        try:
            owner = self.config.get('owner', '')
            repo = self.config.get('repo', '')

            if not owner or not repo:
                return False, "Не настроены данные репозитория"

            # URL для получения последнего релиза
            url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"

            print(f"Проверка обновлений: {url}")

            # Делаем запрос к GitHub API
            response = requests.get(url, timeout=10)

            if response.status_code == 404:
                return False, "Репозиторий или релизы не найдены"
            elif response.status_code != 200:
                return False, f"Ошибка API GitHub: {response.status_code}"

            release_data = response.json()
            latest_version = release_data['tag_name']
            download_url = release_data['zipball_url']  # Ссылка на ZIP-архив

            print(f"Текущая версия: {self.current_version}")
            print(f"Последняя версия: {latest_version}")

            # Сравниваем версии
            if self.is_newer_version(latest_version, self.current_version):
                update_info = {
                    'version': latest_version,
                    'download_url': download_url,
                    'release_notes': release_data.get('body', ''),
                    'published_at': release_data.get('published_at', '')
                }
                return True, update_info
            else:
                return True, "up_to_date"

        except requests.exceptions.Timeout:
            return False, "Таймаут при проверке обновлений"
        except requests.exceptions.ConnectionError:
            return False, "Ошибка подключения к интернету"
        except Exception as e:
            return False, f"Ошибка при проверке обновлений: {str(e)}"

    def is_newer_version(self, latest, current):
        """Сравнить версии"""
        try:
            # Убираем 'v' из версий если есть
            latest = latest.lstrip('vV')
            current = current.lstrip('vV')

            latest_parts = [int(x) for x in latest.split('.')]
            current_parts = [int(x) for x in current.split('.')]

            # Сравниваем по частям
            for i in range(max(len(latest_parts), len(current_parts))):
                latest_num = latest_parts[i] if i < len(latest_parts) else 0
                current_num = current_parts[i] if i < len(current_parts) else 0

                if latest_num > current_num:
                    return True
                elif latest_num < current_num:
                    return False

            return False  # Версии одинаковые
        except:
            # Если не удалось сравнить, считаем что есть обновление
            return latest != current

    def download_update(self, download_url):
        """Скачать обновление"""
        try:
            # Создаем временную папку
            temp_dir = tempfile.mkdtemp()
            zip_path = os.path.join(temp_dir, 'update.zip')

            print(f"Скачивание обновления: {download_url}")

            # Скачиваем ZIP-архив
            response = requests.get(download_url, stream=True, timeout=30)
            response.raise_for_status()

            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            print("Обновление скачано успешно")
            return True, zip_path

        except Exception as e:
            return False, f"Ошибка скачивания: {str(e)}"

    def install_update(self, zip_path):
        """Установить обновление"""
        try:
            # Создаем резервную копию
            backup_success = self.create_backup()

            # Создаем временную папку для распаковки
            extract_dir = tempfile.mkdtemp()

            print(f"Распаковка обновления в: {extract_dir}")

            # Распаковываем архив
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)

            # В распакованной папке будет подпапка вида owner-repo-commitHash/
            extracted_folders = [f for f in os.listdir(extract_dir)
                                 if os.path.isdir(os.path.join(extract_dir, f))]

            if not extracted_folders:
                return False, "Не удалось найти файлы в архиве"

            update_files_dir = os.path.join(extract_dir, extracted_folders[0])

            print(f"Копирование файлов из: {update_files_dir}")

            # Копируем файлы обновления
            self.copy_update_files(update_files_dir, self.script_dir)

            # Обновляем версию в конфиге
            self.update_version_config()

            # Очищаем временные файлы
            shutil.rmtree(extract_dir, ignore_errors=True)
            os.unlink(zip_path)

            print("Обновление установлено успешно")
            return True, "Обновление успешно установлено"

        except Exception as e:
            # Восстанавливаем из резервной копии при ошибке
            if backup_success:
                self.restore_backup()
            return False, f"Ошибка установки обновления: {str(e)}"

    def copy_update_files(self, source_dir, target_dir):
        """Скопировать файлы обновления, сохраняя пользовательские данные"""
        # Файлы и папки которые НЕ нужно перезаписывать
        exclude = [
            'backups',
            'документы',
            'анкеты_данные.xlsx',
            'license.json',
            'settings.ini',
            'repo_config.json',  # Сохраняем настройки репозитория
            'version_config.json',  # Обновим отдельно
            'update.log'
        ]

        for item in os.listdir(source_dir):
            if item in exclude:
                continue

            source_path = os.path.join(source_dir, item)
            target_path = os.path.join(target_dir, item)

            if os.path.isdir(source_path):
                if os.path.exists(target_path):
                    shutil.rmtree(target_path)
                shutil.copytree(source_path, target_path)
            else:
                if os.path.exists(target_path):
                    os.remove(target_path)
                shutil.copy2(source_path, target_path)

    def update_version_config(self):
        """Обновить версию в конфиге после успешного обновления"""
        try:
            version_path = os.path.join(self.script_dir, 'version_config.json')
            with open(version_path, 'r', encoding='utf-8') as f:
                version_data = json.load(f)

            # Версия будет обновлена после перезапуска и проверки нового релиза
            # Пока оставляем как есть
            print("Версия будет обновлена после перезапуска")

        except Exception as e:
            print(f"Ошибка обновления версии: {e}")

    def create_backup(self):
        """Создать резервную копию"""
        try:
            backup_dir = os.path.join(self.script_dir, 'backups')
            os.makedirs(backup_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(backup_dir, f'backup_{timestamp}')

            # Копируем важные файлы
            important_files = [
                'main.py', 'main_window.py', 'settings.py',
                'theme_manager.py', 'widgets.py', 'updater.py',
                'version_config.json', 'repo_config.json',
                'анкеты_данные.xlsx', 'license.json'
            ]

            os.makedirs(backup_path, exist_ok=True)
            for file in important_files:
                src = os.path.join(self.script_dir, file)
                if os.path.exists(src):
                    shutil.copy2(src, backup_path)

            print(f"Резервная копия создана: {backup_path}")
            return True

        except Exception as e:
            print(f"Ошибка создания резервной копии: {e}")
            return False

    def restore_backup(self):
        """Восстановить из резервной копии"""
        try:
            backup_dir = os.path.join(self.script_dir, 'backups')
            if not os.path.exists(backup_dir):
                return False

            # Находим последнюю резервную копию
            backups = [d for d in os.listdir(backup_dir) if d.startswith('backup_')]
            if not backups:
                return False

            latest_backup = sorted(backups)[-1]
            backup_path = os.path.join(backup_dir, latest_backup)

            # Восстанавливаем файлы
            for file in os.listdir(backup_path):
                src = os.path.join(backup_path, file)
                dst = os.path.join(self.script_dir, file)
                if os.path.exists(dst):
                    os.remove(dst)
                shutil.copy2(src, dst)

            print(f"Восстановлено из резервной копии: {latest_backup}")
            return True

        except Exception as e:
            print(f"Ошибка восстановления из резервной копии: {e}")
            return False

    def restart_program(self):
        """Перезапустить программу"""
        try:
            import subprocess
            python = sys.executable
            if getattr(sys, 'frozen', False):
                # Если это собранное приложение
                executable = sys.executable
                subprocess.Popen([executable])
            else:
                # Если это скрипт Python
                script = os.path.join(self.script_dir, 'main.py')
                subprocess.Popen([python, script])

            sys.exit(0)
        except Exception as e:
            print(f"Ошибка перезапуска: {e}")

    def auto_update_from_repo(self):
        """Автоматическое обновление из репозитория"""
        try:
            success, result = self.check_for_updates()
            if success and result != "up_to_date":
                print("Найдены обновления, начинаем установку...")
                return self.download_and_install_update(result)
            return success, "Обновлений не найдено" if result == "up_to_date" else result
        except Exception as e:
            return False, f"Ошибка автоматического обновления: {str(e)}"

    def download_and_install_update(self, update_info):
        """Скачать и установить обновление"""
        try:
            # Скачиваем обновление
            download_success, download_result = self.download_update(update_info['download_url'])
            if not download_success:
                return False, download_result

            # Устанавливаем обновление
            install_success, install_message = self.install_update(download_result)
            return install_success, install_message

        except Exception as e:
            return False, f"Ошибка установки обновления: {str(e)}"