# update_manager.py - ИСПРАВЛЕННАЯ ВЕРСИЯ ДЛЯ СКАЧИВАНИЯ EXE ФАЙЛОВ
import os
import sys
import json
import shutil
import tempfile
import requests
import subprocess
import re
import time
from pathlib import Path
from datetime import datetime
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
                     if f.lower().endswith('.exe')]

        # Пробуем найти наш файл по разным вариантам названия
        preferred_names = ['Программа.exe', 'DocumentFiller.exe', 'Document_Filler.exe']

        for name in preferred_names:
            full_path = os.path.join(self.script_dir, name)
            if os.path.exists(full_path):
                return name

        # Если не нашли предпочтительные имена, берем первый exe файл
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
            if tag_name.startswith('v'):
                tag_name = tag_name[1:]

            version_match = re.search(r'(\d+\.\d+\.\d+)', tag_name)
            if version_match:
                return version_match.group(1)

            version_match = re.search(r'(\d+\.\d+)', tag_name)
            if version_match:
                return version_match.group(1) + '.0'

            return tag_name
        except Exception as e:
            print(f"Ошибка извлечения версии из тега: {e}")
            return tag_name

    def check_for_updates(self):
        """Проверка обновлений через GitHub - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
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

                # Ищем EXE файл в ассетах (assets) релиза
                assets = release_info.get('assets', [])
                exe_asset = None

                print(f"📦 Поиск EXE файла в {len(assets)} ассетах...")

                for asset in assets:
                    asset_name = asset.get('name', '')
                    print(f"  🔍 Проверка ассета: {asset_name}")

                    if asset_name.lower().endswith('.exe'):
                        # Проверяем, содержит ли имя нужные ключевые слова
                        asset_name_lower = asset_name.lower()
                        if ('documentfiller' in asset_name_lower or
                                'программа' in asset_name_lower or
                                'document_filler' in asset_name_lower):
                            exe_asset = asset
                            print(f"✅ Найден подходящий EXE файл: {asset_name}")
                            break
                        else:
                            print(f"⚠️ Найден EXE, но не подходит по имени: {asset_name}")

                if not exe_asset:
                    # Если не нашли по ключевым словам, берем первый EXE файл
                    for asset in assets:
                        if asset.get('name', '').lower().endswith('.exe'):
                            exe_asset = asset
                            print(f"✅ Найден EXE файл (первый попавшийся): {asset.get('name')}")
                            break

                if not exe_asset:
                    return False, "В релизе не найден EXE файл для скачивания"

                # Формируем информацию об обновлении
                update_info = {
                    "version": latest_version,
                    "tag_name": tag_name,
                    "release_notes": release_info.get('body', ''),
                    "release_name": release_info.get('name', ''),
                    "owner": owner,
                    "repo": repo,
                    "exe_url": exe_asset.get('browser_download_url'),
                    "exe_filename": exe_asset.get('name'),
                    "exe_size": exe_asset.get('size', 0),
                    "assets": assets  # Сохраняем все ассеты для отладки
                }

                print(f"✅ Сформирована информация об обновлении:")
                print(f"   • EXE URL: {update_info['exe_url']}")
                print(f"   • Имя файла: {update_info['exe_filename']}")
                print(f"   • Размер: {update_info['exe_size']} байт")

                return True, update_info

            else:
                print(f"ℹ️ Установлена последняя версия: {self.current_version}")
                return True, "up_to_date"

        except requests.exceptions.RequestException as e:
            return False, f"Ошибка сети: {str(e)}"
        except Exception as e:
            return False, f"Ошибка проверки обновлений GitHub: {str(e)}"

    def download_and_install_update(self, update_info, geometry_file=None):
        """Скачать и установить обновление - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        try:
            print("🔄 Начало процесса обновления...")

            if not update_info.get('exe_url'):
                return False, "В информации об обновлении отсутствует URL для скачивания EXE"

            # Создаем временную директорию
            temp_dir = tempfile.mkdtemp(prefix="DocumentFiller_Update_")
            print(f"📁 Временная директория: {temp_dir}")

            # Скачиваем EXE файл
            exe_url = update_info['exe_url']
            exe_filename = update_info['exe_filename'] or f"DocumentFiller_v{update_info['version']}.exe"
            exe_path = os.path.join(temp_dir, exe_filename)

            print(f"⬇️ Скачивание EXE файла: {exe_url}")
            print(f"📁 Сохранение в: {exe_path}")

            # Скачиваем EXE с прогрессом
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/octet-stream'
            }

            response = requests.get(exe_url, headers=headers, stream=True, timeout=60)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0

            print(f"📏 Общий размер файла: {total_size} байт")

            with open(exe_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)

                        if total_size > 0:
                            progress = (downloaded_size / total_size) * 100
                            print(f"📥 Прогресс загрузки: {progress:.1f}% ({downloaded_size}/{total_size} байт)",
                                  end='\r')

            print(f"\n✅ EXE файл скачан: {exe_path} ({downloaded_size} байт)")

            # Проверяем валидность EXE
            if not self.is_valid_exe_file(exe_path):
                # Пробуем переименовать файл
                backup_exe_path = exe_path + ".invalid"
                os.rename(exe_path, backup_exe_path)
                print(f"⚠️ Скачанный файл невалиден. Переименован в: {backup_exe_path}")

                # Пробуем скачать через альтернативный метод
                return self.download_update_alternative(update_info, geometry_file, temp_dir)

            # Получаем путь к текущему EXE
            current_exe = os.path.join(self.script_dir, self.exe_name)
            print(f"🔧 Текущий EXE: {current_exe}")

            # Проверяем, существует ли текущий EXE
            if not os.path.exists(current_exe):
                print(f"⚠️ Текущий EXE не найден: {current_exe}")
                print("🔍 Поиск других EXE файлов...")

                exe_files = [f for f in os.listdir(self.script_dir)
                             if f.lower().endswith('.exe')]

                if exe_files:
                    current_exe = os.path.join(self.script_dir, exe_files[0])
                    self.exe_name = exe_files[0]
                    print(f"✅ Найден альтернативный EXE: {current_exe}")
                else:
                    return False, "Не найден текущий EXE файл для замены"

            # Создаем улучшенный BAT-скрипт для обновления
            bat_script_path = self.create_update_script_improved(
                current_exe, exe_path, temp_dir, geometry_file
            )

            if not bat_script_path:
                return False, "Не удалось создать скрипт обновления"

            print(f"✅ BAT-скрипт создан: {bat_script_path}")

            # Запускаем BAT-скрипт
            print("🚀 Запуск скрипта обновления...")

            # Используем subprocess с CREATE_NEW_CONSOLE чтобы окно было видимым
            CREATE_NEW_CONSOLE = 0x00000010
            subprocess.Popen(
                f'start "" /B "{bat_script_path}"',
                shell=True,
                creationflags=CREATE_NEW_CONSOLE
            )

            return True, "Обновление запущено. Программа закроется и будет обновлена автоматически."

        except Exception as e:
            return False, f"Ошибка установки обновления: {str(e)}"

    def download_update_alternative(self, update_info, geometry_file, temp_dir):
        """Альтернативный метод скачивания обновления"""
        try:
            print("🔄 Попытка альтернативного метода скачивания...")

            tag_name = update_info['tag_name']
            owner = update_info['owner']
            repo = update_info['repo']

            # Пробуем скачать архив с релизом и найти в нем EXE
            zip_url = f"https://github.com/{owner}/{repo}/archive/refs/tags/{tag_name}.zip"
            zip_path = os.path.join(temp_dir, f"{tag_name}.zip")

            print(f"⬇️ Скачивание архива: {zip_url}")

            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(zip_url, headers=headers, stream=True, timeout=60)
            response.raise_for_status()

            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            print(f"✅ Архив скачан: {zip_path}")

            # Распаковываем архив
            extract_dir = os.path.join(temp_dir, "extracted")
            print(f"🗜️ Распаковка архива в: {extract_dir}")

            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)

            # Ищем EXE в распакованных файлах
            print("🔍 Поиск EXE файла в архиве...")

            # Сначала ищем в корне
            exe_path = self.find_exe_in_directory(extract_dir)

            if not exe_path:
                # Ищем в подпапках
                for root, dirs, files in os.walk(extract_dir):
                    for dir_name in dirs:
                        if 'dist' in dir_name.lower() or 'build' in dir_name.lower():
                            subdir = os.path.join(root, dir_name)
                            exe_path = self.find_exe_in_directory(subdir)
                            if exe_path:
                                break
                    if exe_path:
                        break

            if not exe_path:
                return False, "EXE файл не найден в архиве"

            print(f"✅ EXE файл найден: {exe_path}")

            # Проверяем валидность
            if not self.is_valid_exe_file(exe_path):
                return False, "Найденный файл не является валидным EXE"

            # Получаем путь к текущему EXE
            current_exe = os.path.join(self.script_dir, self.exe_name)

            # Создаем скрипт обновления
            bat_script_path = self.create_update_script_improved(
                current_exe, exe_path, temp_dir, geometry_file
            )

            if not bat_script_path:
                return False, "Не удалось создать скрипт обновления"

            print("🚀 Запуск скрипта обновления...")
            CREATE_NEW_CONSOLE = 0x00000010
            subprocess.Popen(
                f'start "" /B "{bat_script_path}"',
                shell=True,
                creationflags=CREATE_NEW_CONSOLE
            )

            return True, "Обновление запущено через альтернативный метод."

        except Exception as e:
            return False, f"Ошибка альтернативного метода: {str(e)}"

    def create_update_script_improved(self, current_exe, new_exe_path, temp_dir, geometry_file=None):
        """Создать УЛУЧШЕННЫЙ BAT-скрипт для обновления"""
        try:
            # Имя файла для использования в командах
            exe_name = os.path.basename(current_exe)
            exe_name_no_ext = os.path.splitext(exe_name)[0]

            # Получаем директорию программы
            program_dir = os.path.dirname(current_exe)

            # Создаем УЛУЧШЕННЫЙ BAT-скрипт
            bat_content = f'''@echo off
chcp 65001 >nul
title DocumentFiller - Обновление программы
echo ===============================================
echo    DocumentFiller - Обновление программы
echo ===============================================
echo.

echo Шаг 1: Определение текущего процесса...
echo Имя файла: {exe_name}
echo Директория: {program_dir}

echo.
echo Шаг 2: Закрытие текущей программы...
echo Пожалуйста, не закрывайте это окно!

REM Закрываем все процессы с похожими именами
:kill_process
echo Попытка закрыть программу...

REM Закрываем по имени файла
taskkill /IM "{exe_name}" /F >nul 2>&1
taskkill /IM "{exe_name_no_ext}.exe" /F >nul 2>&1

REM Закрываем все процессы с похожими именами
for %%a in ("Программа" "DocumentFiller" "Document_Filler") do (
    taskkill /IM "%%~a.exe" /F >nul 2>&1
)

echo Ожидание 3 секунды для завершения процессов...
timeout /t 3 /nobreak >nul

REM Проверяем, остались ли процессы
tasklist /FI "IMAGENAME eq {exe_name}" 2>nul | find /I "{exe_name}" >nul
if not errorlevel 1 (
    echo Процесс еще активен, повторяем попытку...
    goto kill_process
)

echo Все процессы успешно закрыты!
echo.

echo Шаг 3: Замена файла программы...
:replace_file
echo Замена файла {exe_name}...

REM Делаем несколько попыток копирования
set attempts=0
:copy_loop
set /a attempts+=1
echo Попытка копирования #%attempts%

copy /Y "{new_exe_path}" "{current_exe}" >nul 2>&1
if errorlevel 1 (
    if %attempts% geq 5 (
        echo Ошибка: Не удалось заменить файл после 5 попыток
        pause
        exit /b 1
    )
    echo Файл еще занят, ожидаем 2 секунды...
    timeout /t 2 /nobreak >nul
    goto copy_loop
)

echo Файл успешно заменен!
echo.

echo Шаг 4: Восстановление конфигурации...
REM Восстанавливаем геометрию окна, если есть
if exist "{geometry_file}" (
    copy /Y "{geometry_file}" "{program_dir}\\window_geometry.json" >nul 2>&1
    echo Геометрия окна восстановлена
)

echo Шаг 5: Очистка временных файлов...
if exist "{temp_dir}" (
    rmdir /s /q "{temp_dir}" >nul 2>&1
    echo Временные файлы удалены
)

echo.
echo Шаг 6: Запуск обновленной программы...
echo Запуск новой версии...

REM Запускаем новую версию программы
start "" /D "{program_dir}" "{exe_name}"

echo.
echo Шаг 7: Обновление завершено успешно!
echo Новая версия программы запущена!
echo.

echo Закрытие этого окна через 5 секунд...
timeout /t 5 /nobreak >nul

REM Удаляем этот скрипт
del "%~f0"
exit
'''

            bat_path = os.path.join(self.script_dir, "update_documentfiller.bat")
            with open(bat_path, 'w', encoding='utf-8') as f:
                f.write(bat_content)

            return bat_path

        except Exception as e:
            print(f"❌ Ошибка создания BAT-скрипта: {e}")
            return None

    def find_exe_in_directory(self, directory):
        """Найти EXE файл в директории и поддиректориях"""
        try:
            # Сначала ищем файл с именем DocumentFiller
            for root, dirs, files in os.walk(directory):
                for file in files:
                    file_lower = file.lower()
                    if (file_lower == 'программа.exe' or
                            'documentfiller' in file_lower or
                            'document_filler' in file_lower):
                        exe_path = os.path.join(root, file)
                        print(f"🔍 Найден EXE: {exe_path}")
                        return exe_path

            # Если не нашли, ищем любой EXE файл
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if file.lower().endswith('.exe'):
                        exe_path = os.path.join(root, file)
                        print(f"🔍 Найден EXE (любой): {exe_path}")
                        return exe_path

            return None
        except Exception as e:
            print(f"❌ Ошибка поиска EXE файла: {e}")
            return None

    def is_valid_exe_file(self, file_path):
        """Проверить, является ли файл валидным EXE"""
        try:
            if not os.path.exists(file_path):
                print(f"❌ Файл не существует: {file_path}")
                return False

            file_size = os.path.getsize(file_path)
            print(f"📏 Размер файла: {file_size} байт")

            if file_size < 1024 * 1024:  # Меньше 1 MB - подозрительно
                print(f"⚠️ Файл слишком мал: {file_size} байт")
                # Но все равно проверим сигнатуру

            if file_size > 1024 * 1024 * 100:  # Больше 100 MB - подозрительно
                print(f"⚠️ Файл слишком велик: {file_size} байт")
                # Но все равно проверим сигнатуру

            with open(file_path, 'rb') as f:
                header = f.read(2)
                if header != b'MZ':
                    print(f"❌ Неверная сигнатура EXE файла: {header}")
                    # Смотрим, что это за файл
                    f.seek(0)
                    first_100 = f.read(100).decode('ascii', errors='ignore')
                    if 'html' in first_100.lower() or '<!doctype' in first_100.lower():
                        print("⚠️ Скачан HTML файл вместо EXE")
                    elif 'zip' in first_100.lower() or 'PK' in first_100:
                        print("⚠️ Скачан ZIP файл вместо EXE")
                    return False

            print("✅ Файл является валидным EXE")
            return True

        except Exception as e:
            print(f"❌ Ошибка проверки EXE файла: {e}")
            return False

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
            version_clean = re.sub(r'[^0-9.]', '', version_str)

            parts = version_clean.split('.')

            while len(parts) < 3:
                parts.append('0')

            return tuple(int(part) for part in parts[:3])

        except Exception as e:
            print(f"Ошибка нормализации версии: {e}")
            return (0, 0, 0)

    def get_update_info(self):
        """Получить информацию об обновлении (для обратной совместимости)"""
        return self.check_for_updates()