# update_manager.py - ИСПРАВЛЕННАЯ ВЕРСИЯ С ПРАВИЛЬНЫМ СРАВНЕНИЕМ ВЕРСИЙ
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

            # Пробуем разные способы извлечения версии
            latest_version = self.extract_version_from_tag(tag_name)

            if not latest_version:
                return False, f"Не удалось извлечь версию из тега: {tag_name}"

            print(f"📋 Извлеченная версия: {latest_version}")
            print(f"📋 Текущая версия: {self.current_version}")

            # Сравниваем версии
            if self.is_newer_version(latest_version, self.current_version):
                print(f"🎉 Найдена новая версия: {latest_version} > {self.current_version}")

                # Ищем EXE файл в ассетах - РАСШИРЕННЫЙ ПОИСК
                exe_asset = None
                assets = release_info.get('assets', [])

                print(f"📦 Найдено ассетов в релизе: {len(assets)}")

                # Выводим список всех ассетов для отладки
                for i, asset in enumerate(assets):
                    print(f"   {i + 1}. {asset['name']} ({asset.get('size', 0)} bytes)")

                # Приоритеты поиска EXE файлов
                search_patterns = [
                    lambda name: name.endswith('.exe') and 'documentfiller' in name.lower(),
                    lambda name: name.endswith('.exe') and 'document' in name.lower(),
                    lambda name: name.endswith('.exe') and 'filler' in name.lower(),
                    lambda name: name.endswith('.exe') and 'setup' in name.lower(),
                    lambda name: name.endswith('.exe') and 'install' in name.lower(),
                    lambda name: name.endswith('.exe')  # Любой EXE файл
                ]

                for pattern in search_patterns:
                    for asset in assets:
                        if pattern(asset['name'].lower()):
                            exe_asset = asset
                            print(f"✅ Найден подходящий EXE: {asset['name']}")
                            break
                    if exe_asset:
                        break

                if not exe_asset:
                    # Если EXE не найден, ищем ZIP архив
                    zip_asset = None
                    for asset in assets:
                        if asset['name'].endswith('.zip') and 'documentfiller' in asset['name'].lower():
                            zip_asset = asset
                            print(f"✅ Найден ZIP архив: {asset['name']}")
                            break

                    if zip_asset:
                        # Скачиваем и извлекаем EXE из ZIP
                        return self.handle_zip_update(zip_asset, latest_version)
                    else:
                        return False, "В релизе не найдены EXE файлы или ZIP архивы с программой"

                info = {
                    "version": latest_version,
                    "download_url": exe_asset['browser_download_url'],
                    "release_notes": release_info.get('body', ''),
                    "release_name": release_info.get('name', ''),
                    "update_type": "github",
                    "asset_name": exe_asset['name'],
                    "tag_name": tag_name
                }
                return True, info
            else:
                print(f"ℹ️ Установлена последняя версия: {self.current_version}")
                return True, "up_to_date"

        except requests.exceptions.RequestException as e:
            return False, f"Ошибка сети: {str(e)}"
        except Exception as e:
            return False, f"Ошибка проверки обновлений GitHub: {str(e)}"

    def extract_version_from_tag(self, tag):
        """Извлечь версию из тега GitHub"""
        try:
            # Удаляем префикс 'v' если есть
            clean_tag = tag.lstrip('vV')

            # Пробуем разные паттерны для извлечения версии
            patterns = [
                r'(\d+\.\d+\.\d+)',  # 1.0.31
                r'(\d+\.\d+)',  # 1.0
                r'(\d+)'  # 1
            ]

            for pattern in patterns:
                match = re.search(pattern, clean_tag)
                if match:
                    return match.group(1)

            # Если ничего не нашли, возвращаем очищенный тег
            return clean_tag
        except Exception as e:
            print(f"❌ Ошибка извлечения версии из тега '{tag}': {e}")
            return None

    def handle_zip_update(self, zip_asset, version):
        """Обработать обновление из ZIP архива"""
        try:
            print(f"📦 Обработка ZIP архива: {zip_asset['name']}")

            info = {
                "version": version,
                "download_url": zip_asset['browser_download_url'],
                "release_notes": f"Обновление версии {version} (ZIP архив)",
                "release_name": f"DocumentFiller v{version}",
                "update_type": "github_zip",
                "asset_name": zip_asset['name'],
                "is_zip": True
            }
            return True, info

        except Exception as e:
            return False, f"Ошибка обработки ZIP архива: {str(e)}"

    def download_from_github(self, url, asset_name):
        """Скачать обновление с GitHub"""
        try:
            temp_dir = tempfile.mkdtemp()
            file_name = asset_name
            file_path = os.path.join(temp_dir, file_name)

            print(f"📥 Скачивание с GitHub: {url}")
            print(f"📁 Временный путь: {file_path}")

            headers = {
                'User-Agent': 'DocumentFiller-Updater/1.0',
                'Accept': 'application/octet-stream'
            }

            response = requests.get(url, headers=headers, stream=True, timeout=30)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0

            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)

                        if total_size > 0:
                            percent = (downloaded_size / total_size) * 100
                            print(f"📥 Прогресс: {percent:.1f}% ({downloaded_size}/{total_size} байт)", end='\r')

            print()

            # Проверяем файл
            file_size = os.path.getsize(file_path)
            print(f"📊 Размер скачанного файла: {file_size} байт")

            if file_name.endswith('.exe') and not self.is_valid_exe_file(file_path):
                return False, "Скачанный файл не является корректным EXE"

            print(f"✅ Файл успешно скачан: {file_path}")
            return True, file_path

        except Exception as e:
            return False, f"Ошибка скачивания с GitHub: {str(e)}"

    def extract_exe_from_zip(self, zip_path):
        """Извлечь EXE файл из ZIP архива"""
        try:
            temp_dir = tempfile.mkdtemp()
            print(f"🗜️ Распаковка ZIP архива: {zip_path}")

            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Ищем EXE файлы в архиве
                exe_files = [f for f in zip_ref.namelist() if f.endswith('.exe') and 'documentfiller' in f.lower()]

                # Если не нашли по имени, берем первый EXE
                if not exe_files:
                    exe_files = [f for f in zip_ref.namelist() if f.endswith('.exe')]

                if not exe_files:
                    return False, "В ZIP архиве не найдены EXE файлы"

                # Извлекаем первый найденный EXE
                exe_file = exe_files[0]
                print(f"📁 Найден EXE в архиве: {exe_file}")

                zip_ref.extract(exe_file, temp_dir)
                extracted_path = os.path.join(temp_dir, exe_file)

                # Если файл находится во вложенной папке, находим его полный путь
                if os.path.isdir(extracted_path):
                    for root, dirs, files in os.walk(extracted_path):
                        for file in files:
                            if file.endswith('.exe'):
                                extracted_path = os.path.join(root, file)
                                break

                if not os.path.isfile(extracted_path):
                    return False, "Не удалось извлечь EXE файл из архива"

                print(f"✅ EXE извлечен: {extracted_path}")
                return True, extracted_path

        except Exception as e:
            return False, f"Ошибка распаковки ZIP: {str(e)}"

    def install_update(self, update_info):
        """Установить обновление"""
        try:
            print("🔄 Начало установки обновления...")

            backup_made = self.create_backup()
            if not backup_made:
                print("⚠️ Предупреждение: не удалось создать резервную копию")

            download_url = update_info.get("download_url")
            asset_name = update_info.get("asset_name", "DocumentFiller.exe")
            is_zip = update_info.get("is_zip", False)

            if not download_url:
                return False, "Не указана ссылка для скачивания"

            print(f"📥 Скачивание обновления из GitHub...")

            success, result = self.download_from_github(download_url, asset_name)
            if not success:
                return False, result

            downloaded_file = result

            if not os.path.exists(downloaded_file):
                return False, "Файл не был скачан"

            # Если это ZIP архив, извлекаем EXE
            if is_zip:
                print("🗜️ Обнаружен ZIP архив, извлекаем EXE...")
                success, result = self.extract_exe_from_zip(downloaded_file)
                if not success:
                    return False, result
                downloaded_file = result

            bat_content = self.create_update_bat_script(downloaded_file)

            bat_path = os.path.join(self.script_dir, "apply_update.bat")
            with open(bat_path, "w", encoding="utf-8") as f:
                f.write(bat_content)

            print("🚀 Запуск процесса обновления...")

            try:
                subprocess.Popen(['cmd', '/c', bat_path], cwd=self.script_dir, shell=True)
            except Exception as e:
                print(f"❌ Ошибка запуска BAT: {e}")
                # Альтернативный способ запуска
                os.system(f'start "" "{bat_path}"')

            sys.exit(0)
            return True, "Запущена установка обновления"

        except Exception as e:
            return False, f"Ошибка установки обновления: {e}"

    def is_valid_exe_file(self, file_path):
        """Проверить, что файл является корректным EXE"""
        try:
            file_size = os.path.getsize(file_path)
            if file_size < 2 * 1024 * 1024:  # Минимум 2 МБ
                return False

            # Проверяем сигнатуру EXE файла
            with open(file_path, 'rb') as f:
                header = f.read(2)
                # EXE файлы начинаются с 'MZ'
                if header != b'MZ':
                    return False

            return True
        except:
            return False

    def create_update_bat_script(self, downloaded_file):
        """Создать BAT скрипт для обновления"""
        return f'''@echo off
chcp 65001 >nul
title Обновление DocumentFiller
echo =======================================
echo    Установка обновления DocumentFiller  
echo =======================================
echo.

echo [1/7] Ожидание завершения текущей программы...
timeout /t 3 /nobreak >nul

echo [2/7] Завершение процесса {self.exe_name}...
taskkill /f /im "{self.exe_name}" >nul 2>&1

echo [3/7] Ожидание освобождения файлов...
timeout /t 3 /nobreak >nul

echo [4/7] Проверка нового файла...
if not exist "{downloaded_file}" (
    echo ОШИБКА: Файл обновления не найден!
    pause
    exit /b 1
)

echo [5/7] Копирование нового EXE...
copy /Y "{downloaded_file}" "{os.path.join(self.script_dir, self.exe_name)}" >nul
if %errorlevel% neq 0 (
    echo ОШИБКА: Не удалось скопировать файл!
    pause
    exit /b 1
)

echo [6/7] Проверка нового EXЕ...
if not exist "{os.path.join(self.script_dir, self.exe_name)}" (
    echo ОШИБКА: Новый EXE не создан!
    pause
    exit /b 1
)

echo [7/7] Запуск обновленной программы...
cd /d "{self.script_dir}"
start "" "{os.path.join(self.script_dir, self.exe_name)}"

echo Обновление успешно завершено!
timeout /t 2 >nul

echo Удаление временных файлов...
del /q "{downloaded_file}" >nul 2>&1
rd /q /s "{os.path.dirname(downloaded_file)}" >nul 2>&1

del /q "%~f0" >nul 2>&1
'''

    def create_backup(self):
        """Создать резервную копию"""
        try:
            backup_dir = os.path.join(self.script_dir, "backups")
            os.makedirs(backup_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = os.path.join(backup_dir, f"backup_{ts}")
            os.makedirs(dest, exist_ok=True)

            important_files = [
                "repo_config.json", "анкеты_данные.xlsx",
                "license.json", self.exe_name
            ]

            copied = 0
            for name in important_files:
                src = os.path.join(self.script_dir, name)
                if os.path.exists(src):
                    try:
                        shutil.copy2(src, os.path.join(dest, name))
                        copied += 1
                    except Exception as e:
                        print(f"Ошибка копирования {name}: {e}")

            print(f"✅ Резервная копия создана: {dest} ({copied} файлов)")
            return True
        except Exception as e:
            print(f"❌ Ошибка создания резервной копии: {e}")
            return False

    def download_and_install_update(self, update_info):
        """Полный цикл обновления"""
        try:
            print("🔄 Начало процесса обновления...")
            return self.install_update(update_info)

        except Exception as e:
            return False, f"Ошибка обновления: {e}"

    def is_newer_version(self, latest, current):
        """Сравнение версий - УЛУЧШЕННАЯ ВЕРСИЯ"""
        try:
            print(f"🔍 Сравнение версий: '{latest}' vs '{current}'")

            # Нормализуем версии
            latest_normalized = self.normalize_version(latest)
            current_normalized = self.normalize_version(current)

            print(f"🔍 Нормализованные версии: '{latest_normalized}' vs '{current_normalized}'")

            # Разбиваем на части
            latest_parts = latest_normalized.split('.')
            current_parts = current_normalized.split('.')

            # Дополняем нулями до одинаковой длины
            max_len = max(len(latest_parts), len(current_parts))
            latest_parts.extend(['0'] * (max_len - len(latest_parts)))
            current_parts.extend(['0'] * (max_len - len(current_parts)))

            print(f"🔍 Части версий: latest={latest_parts}, current={current_parts}")

            # Сравниваем каждую часть
            for i in range(max_len):
                latest_num = int(latest_parts[i])
                current_num = int(current_parts[i])

                if latest_num > current_num:
                    print(f"🔍 Версия {latest} НОВЕЕ чем {current}")
                    return True
                elif latest_num < current_num:
                    print(f"🔍 Версия {latest} СТАРШЕ чем {current}")
                    return False

            # Если все части равны
            print(f"🔍 Версии {latest} и {current} РАВНЫ")
            return False

        except Exception as e:
            print(f"❌ Ошибка сравнения версий: {e}")
            # В случае ошибки сравниваем как строки
            return latest > current

    def normalize_version(self, version):
        """Нормализовать версию для сравнения"""
        # Удаляем все нецифровые символы, кроме точек
        cleaned = re.sub(r'[^\d.]', '', version)

        # Убеждаемся, что версия начинается с цифры
        if not cleaned:
            return "0"

        # Удаляем ведущие нули из каждой части
        parts = cleaned.split('.')
        normalized_parts = []

        for part in parts:
            if part:  # Если часть не пустая
                # Удаляем ведущие нули
                normalized_part = part.lstrip('0')
                if not normalized_part:  # Если после удаления нулей ничего не осталось
                    normalized_part = '0'
                normalized_parts.append(normalized_part)
            else:
                normalized_parts.append('0')

        return '.'.join(normalized_parts)

    def get_update_info(self):
        """Получить информацию о настройках обновлений"""
        return {
            "type": self.config.get("type", "github"),
            "github_repo": self.config.get("github_repo", ""),
            "current_version": self.current_version
        }