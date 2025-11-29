# update_manager.py - ИСПРАВЛЕННАЯ ВЕРСИЯ ДЛЯ СКАЧИВАНИЯ АРХИВОВ С GITHUB
import os
import sys
import json
import shutil
import tempfile
import requests
import subprocess
import re
from pathlib import Path
from datetime import datetime
import urllib.parse
import zipfile


class UpdateManager:
    def __init__(self, exe_name=None):
        self.script_dir = self.get_script_dir()
        self.config = self.load_config()
        self.current_version = self.get_current_version()

        if exe_name:
            self.exe_name = exe_name
        else:
            self.exe_name = self.find_exe_name()

    def find_exe_name(self):
        """Автоматически найти имя EXE файла в директории"""
        exe_files = [f for f in os.listdir(self.script_dir)
                     if f.endswith('.exe') and 'DocumentFiller' in f]

        if exe_files:
            return exe_files[0]
        else:
            return "DocumentFiller.exe"

    def get_script_dir(self):
        """Возвращает директорию приложения"""
        if getattr(sys, "frozen", False):
            return os.path.dirname(sys.executable)
        else:
            return os.path.dirname(os.path.abspath(__file__))

    def load_config(self):
        """Загрузить repo_config.json"""
        try:
            config_path = os.path.join(self.script_dir, "repo_config.json")
            if not os.path.exists(config_path):
                # Конфиг по умолчанию для GitHub
                default_config = {
                    "type": "github",
                    "github_repo": "https://github.com/vavilon1205/DocumentFiller",
                    "current_version": "1.0.0",
                    "update_url": "https://github.com/vavilon1205/DocumentFiller/releases/latest",
                    "online_license_db_url": ""
                }
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(default_config, f, indent=2, ensure_ascii=False)
                return default_config

            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Ошибка загрузки repo_config.json: {e}")
            return {}

    def get_current_version(self):
        """Получить текущую версию"""
        try:
            try:
                from version import __version__
                return __version__
            except ImportError:
                pass

            return self.config.get("current_version", "1.0.0")
        except Exception as e:
            print(f"Ошибка получения версии: {e}")
            return "1.0.0"

    def extract_version_from_tag(self, tag_name):
        """Извлечь версию из тега GitHub"""
        try:
            # Убираем префикс 'v' если есть
            if tag_name.startswith('v'):
                tag_name = tag_name[1:]

            # Ищем версию в формате X.Y.Z
            version_match = re.search(r'(\d+\.\d+\.\d+)', tag_name)
            if version_match:
                return version_match.group(1)

            # Пробуем другие форматы
            version_match = re.search(r'(\d+\.\d+)', tag_name)
            if version_match:
                return version_match.group(1) + '.0'

            return tag_name
        except Exception as e:
            print(f"Ошибка извлечения версии из тега: {e}")
            return tag_name

    def download_and_extract_from_source_zip(self, owner, repo, tag_name, latest_version):
        """Скачать и извлечь EXE из архива исходного кода"""
        try:
            # Формируем URL архива исходного кода
            source_zip_url = f"https://github.com/{owner}/{repo}/archive/refs/tags/{tag_name}.zip"
            print(f"🔗 Ссылка на архив исходного кода: {source_zip_url}")

            # Создаем временную директорию
            temp_dir = tempfile.mkdtemp()
            zip_path = os.path.join(temp_dir, f"{tag_name}.zip")

            print(f"⬇️ Скачивание архива исходного кода...")

            # Скачиваем архив
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            response = requests.get(source_zip_url, headers=headers, stream=True, timeout=30)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0

            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        if total_size > 0:
                            progress = (downloaded_size / total_size) * 100
                            print(f"📥 Прогресс загрузки: {progress:.1f}%", end='\r')

            print(f"\n✅ Архив скачан: {zip_path} ({downloaded_size} bytes)")

            # Извлекаем EXE из архива
            exe_path = self.extract_exe_from_source_zip(zip_path, temp_dir)
            if exe_path and os.path.exists(exe_path):
                print(f"✅ EXE файл найден: {exe_path}")

                info = {
                    "version": latest_version,
                    "download_url": source_zip_url,
                    "release_notes": f"Обновление до версии {latest_version}",
                    "release_name": f"DocumentFiller v{latest_version}",
                    "update_type": "github_source_zip",
                    "asset_name": f"{tag_name}.zip",
                    "extracted_exe_path": exe_path
                }
                return True, info
            else:
                return False, "EXE файл не найден в архиве исходного кода"

        except requests.exceptions.RequestException as e:
            return False, f"Ошибка скачивания архива: {str(e)}"
        except Exception as e:
            return False, f"Ошибка обработки архива: {str(e)}"
        finally:
            # Временные файлы будут очищены после установки обновления
            pass

    def extract_exe_from_source_zip(self, zip_path, extract_to):
        """Извлечь EXE файл из архива исходного кода"""
        try:
            print(f"🗜️ Извлечение архива: {zip_path}")

            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Получаем список всех файлов в архиве
                all_files = zip_ref.namelist()
                print(f"📁 Всего файлов в архиве: {len(all_files)}")

                # Ищем EXE файлы в архиве
                exe_files = [f for f in all_files if f.lower().endswith('.exe')]

                print(f"🔍 Найдено EXE файлов: {len(exe_files)}")
                for exe_file in exe_files:
                    print(f"   - {exe_file}")

                if not exe_files:
                    # Если EXE не найдены, ищем в поддиректориях
                    print("🔍 Поиск EXE в поддиректориях...")
                    for file_path in all_files:
                        if '/dist/' in file_path.replace('\\', '/') and file_path.lower().endswith('.exe'):
                            exe_files.append(file_path)
                            print(f"   - {file_path} (в dist)")

                if not exe_files:
                    return None

                # Извлекаем и проверяем все EXE файлы
                for exe_file in exe_files:
                    try:
                        print(f"📦 Извлечение: {exe_file}")

                        # Создаем директорию для извлечения
                        os.makedirs(extract_to, exist_ok=True)

                        # Извлекаем файл
                        zip_ref.extract(exe_file, extract_to)
                        extracted_path = os.path.join(extract_to, exe_file)

                        # Нормализуем путь
                        extracted_path = os.path.normpath(extracted_path)

                        print(f"📁 Извлеченный путь: {extracted_path}")

                        # Проверяем, что файл существует и является валидным EXE
                        if os.path.exists(extracted_path) and self.is_valid_exe_file(extracted_path):
                            print(f"✅ Валидный EXE найден: {extracted_path}")
                            return extracted_path
                        else:
                            print(f"⚠️ Файл не является валидным EXE: {extracted_path}")
                            if os.path.exists(extracted_path):
                                os.remove(extracted_path)
                    except Exception as e:
                        print(f"⚠️ Ошибка извлечения {exe_file}: {e}")
                        continue

                print("❌ Не найден валидный EXE файл в архиве")
                return None

        except Exception as e:
            print(f"❌ Ошибка извлечения архива: {e}")
            return None

    def install_update(self, update_info):
        """Установить обновление"""
        try:
            print("🔄 Начало установки обновления...")

            # Создаем резервную копию
            backup_path = self.create_backup()
            if not backup_path:
                return False, "Не удалось создать резервную копию"

            # Получаем путь к текущему EXE
            current_exe = os.path.join(self.script_dir, self.exe_name)

            # Определяем путь к новому EXE
            if update_info.get('update_type') in ['github_zip', 'github_source_zip']:
                new_exe = update_info.get('extracted_exe_path')
                if not new_exe or not os.path.exists(new_exe):
                    return False, "Не найден EXE файл для обновления"
            else:
                # Скачиваем новый EXE
                temp_dir = tempfile.mkdtemp()
                new_exe = os.path.join(temp_dir, update_info.get('asset_name', 'update.exe'))
                if not self.download_from_github(update_info, new_exe):
                    return False, "Не удалось скачать обновление"

            # Проверяем новый EXE
            if not self.is_valid_exe_file(new_exe):
                return False, "Скачанный файл не является валидным EXE"

            # Создаем BAT скрипт для обновления
            bat_script = self.create_update_bat_script(new_exe, current_exe, backup_path)
            if not bat_script:
                return False, "Не удалось создать скрипт обновления"

            print("✅ Подготовка обновления завершена")
            return True, bat_script

        except Exception as e:
            return False, f"Ошибка установки обновления: {str(e)}"

    def is_valid_exe_file(self, file_path):
        """Проверить, является ли файл валидным EXE"""
        try:
            if not os.path.exists(file_path):
                print(f"❌ Файл не существует: {file_path}")
                return False

            # Проверяем размер файла (должен быть больше 1MB)
            file_size = os.path.getsize(file_path)
            print(f"📏 Размер файла: {file_size} bytes")

            if file_size < 1024 * 1024:
                print(f"❌ Файл слишком мал: {file_size} bytes")
                return False

            # Проверяем сигнатуру EXE файла
            with open(file_path, 'rb') as f:
                header = f.read(2)
                if header != b'MZ':
                    print("❌ Неверная сигнатура EXE файла")
                    return False

            print("✅ Файл является валидным EXE")
            return True

        except Exception as e:
            print(f"❌ Ошибка проверки EXE файла: {e}")
            return False

    def create_update_bat_script(self, new_exe, current_exe, backup_path):
        """Создать BAT скрипт для обновления"""
        try:
            bat_content = f"""@echo off
chcp 65001 >nul
echo Установка обновления DocumentFiller...
timeout /t 2 /nobreak >nul

echo Создание резервной копии...
copy "{current_exe}" "{backup_path}" >nul 2>&1

echo Замена файла...
taskkill /IM "{os.path.basename(current_exe)}" /F >nul 2>&1
timeout /t 1 /nobreak >nul
del "{current_exe}" >nul 2>&1
copy "{new_exe}" "{current_exe}" >nul 2>&1

echo Обновление завершено!
echo Запуск программы...
start "" "{current_exe}"

del "%~f0"
"""
            bat_path = os.path.join(self.script_dir, "update.bat")
            with open(bat_path, 'w', encoding='utf-8') as f:
                f.write(bat_content)

            return bat_path

        except Exception as e:
            print(f"❌ Ошибка создания BAT скрипта: {e}")
            return None

    def create_backup(self):
        """Создать резервную копию текущей версии"""
        try:
            current_exe = os.path.join(self.script_dir, self.exe_name)
            if not os.path.exists(current_exe):
                return None

            backup_dir = os.path.join(self.script_dir, "backup")
            os.makedirs(backup_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{self.exe_name}.backup.{timestamp}"
            backup_path = os.path.join(backup_dir, backup_name)

            shutil.copy2(current_exe, backup_path)
            print(f"✅ Создана резервная копия: {backup_path}")

            return backup_path

        except Exception as e:
            print(f"❌ Ошибка создания резервной копии: {e}")
            return None

    def download_and_install_update(self, update_info):
        """Скачать и установить обновление"""
        try:
            success, result = self.install_update(update_info)
            if not success:
                return False, result

            # Запускаем BAT скрипт
            bat_script = result
            print(f"🚀 Запуск скрипта обновления: {bat_script}")
            subprocess.Popen([bat_script], shell=True)

            return True, "Обновление запущено, программа будет перезапущена"

        except Exception as e:
            return False, f"Ошибка установки обновления: {str(e)}"

    def is_newer_version(self, version1, version2):
        """Сравнить версии, вернуть True если version1 новее version2"""
        try:
            v1_parts = self.normalize_version(version1)
            v2_parts = self.normalize_version(version2)

            return v1_parts > v2_parts

        except Exception as e:
            print(f"Ошибка сравнения версий: {e}")
            return False

    def normalize_version(self, version_str):
        """Нормализовать версию для сравнения"""
        try:
            # Убираем нечисловые префиксы и суффиксы
            version_clean = re.sub(r'[^0-9.]', '', version_str)

            # Разбиваем на части
            parts = version_clean.split('.')

            # Дополняем нулями до 3 частей
            while len(parts) < 3:
                parts.append('0')

            # Преобразуем в числа
            return tuple(int(part) for part in parts[:3])

        except Exception as e:
            print(f"Ошибка нормализации версии: {e}")
            return (0, 0, 0)

    def get_update_info(self):
        """Получить информацию об обновлении (для обратной совместимости)"""
        return self.check_for_updates()

    def check_for_updates(self):
        """Проверка обновлений через GitHub"""
        try:
            github_repo = self.config.get("github_repo", "").strip()
            if not github_repo:
                return False, "Не указан GitHub репозиторий"

            print(f"🔍 Проверка обновлений в GitHub: {github_repo}")
            print(f"🔍 Текущая версия программы: {self.current_version}")

            # Извлекаем владельца и имя репозитория из URL
            repo_parts = github_repo.rstrip('/').split('/')
            if len(repo_parts) < 2:
                return False, "Неверный формат URL репозитория"

            owner = repo_parts[-2]
            repo = repo_parts[-1]

            # Получаем информацию о последнем релизе через GitHub API
            api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"

            headers = {
                'User-Agent': 'DocumentFiller-Updater/1.0',
                'Accept': 'application/vnd.github.v3+json'
            }

            print(f"🔗 Запрос к GitHub API: {api_url}")
            response = requests.get(api_url, headers=headers, timeout=10)

            if response.status_code == 404:
                return False, "Релизы не найдены или репозиторий не существует"
            elif response.status_code != 200:
                return False, f"Ошибка GitHub API: {response.status_code} - {response.text}"

            release_info = response.json()

            # Извлекаем версию из тега
            tag_name = release_info['tag_name']
            print(f"🔍 Тег релиза: {tag_name}")

            # Извлекаем версию
            latest_version = self.extract_version_from_tag(tag_name)

            if not latest_version:
                return False, f"Не удалось извлечь версию из тега: {tag_name}"

            print(f"📋 Последняя версия на GitHub: {latest_version}")
            print(f"📋 Текущая версия программы: {self.current_version}")

            # Сравниваем версии
            if self.is_newer_version(latest_version, self.current_version):
                print(f"🎉 Найдена новая версия: {latest_version} > {self.current_version}")

                # Сразу пытаемся скачать архив исходного кода
                print("🔍 Попытка скачать архив исходного кода...")
                return self.download_and_extract_from_source_zip(owner, repo, tag_name, latest_version)

            else:
                print(f"ℹ️ Установлена последняя версия: {self.current_version}")
                return True, "up_to_date"

        except requests.exceptions.RequestException as e:
            return False, f"Ошибка сети: {str(e)}"
        except Exception as e:
            return False, f"Ошибка проверки обновлений GitHub: {str(e)}"

    def download_from_github(self, asset, destination):
        """Скачать файл с GitHub (для обратной совместимости)"""
        try:
            print(f"⬇️ Скачивание: {asset['browser_download_url']}")
            response = requests.get(asset['browser_download_url'], stream=True, timeout=30)
            response.raise_for_status()

            with open(destination, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            print(f"✅ Файл скачан: {destination}")
            return True

        except Exception as e:
            print(f"❌ Ошибка скачивания: {e}")
            return False