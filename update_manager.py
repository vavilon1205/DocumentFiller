# update_manager.py - ИСПРАВЛЕННАЯ ВЕРСИЯ ДЛЯ ОБНОВЛЕНИЯ
import os
import sys
import json
import shutil
import tempfile
import requests
import subprocess
from pathlib import Path
from datetime import datetime
import urllib.parse


class UpdateManager:
    def __init__(self, exe_name=None):
        self.script_dir = self.get_script_dir()
        self.config = self.load_config()
        self.current_version = self.get_current_version()

        # Определяем имя EXE файла автоматически
        if exe_name:
            self.exe_name = exe_name
        else:
            self.exe_name = self.find_exe_name()

    def find_exe_name(self):
        """Автоматически найти имя EXE файла в директории"""
        exe_files = [f for f in os.listdir(self.script_dir)
                     if f.endswith('.exe') and f.startswith('DocumentFiller')]

        if exe_files:
            return exe_files[0]  # Берем первый найденный EXE
        else:
            return "DocumentFiller.exe"  # Fallback

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
                    "type": "yandex_disk",
                    "yandex_disk_url": "",
                    "current_version": "1.0.0",
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
        """Получить текущую версию из repo_config.json"""
        return self.config.get("current_version", "1.0.0")

    def check_for_updates(self):
        """Проверка обновлений - только Яндекс.Диск"""
        try:
            yandex_url = self.config.get("yandex_disk_url", "").strip()
            if not yandex_url:
                return False, "Не указана ссылка на Яндекс.Диск в repo_config.json"

            # Для Яндекс.Диска просто возвращаем информацию о доступном обновлении
            info = {
                "version": self.extract_version_from_url(yandex_url) or self.get_current_version(),
                "download_url": yandex_url,
                "update_type": "yandex_disk",
                "release_notes": "Автоматическое обновление с Яндекс.Диска"
            }

            # Проверяем, есть ли новая версия
            latest_version = info["version"]
            if self.is_newer_version(latest_version, self.current_version):
                return True, info
            else:
                return True, "up_to_date"

        except Exception as e:
            return False, f"Ошибка проверки обновлений: {e}"

    def extract_version_from_url(self, url):
        """Извлечь версию из URL"""
        try:
            import re
            patterns = [
                r'v?(\d+\.\d+\.\d+)',
                r'v?(\d+\.\d+)',
                r'v?(\d+)'
            ]

            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    return match.group(1)

            return None
        except:
            return None

    def is_newer_version(self, latest, current):
        """Сравнение версий"""
        try:
            def parts(v):
                return [int(x) for x in v.split(".") if x.isdigit()]

            lp = parts(latest)
            cp = parts(current)
            for i in range(max(len(lp), len(cp))):
                lv = lp[i] if i < len(lp) else 0
                cv = cp[i] if i < len(cp) else 0
                if lv > cv:
                    return True
                if lv < cv:
                    return False
            return False
        except:
            return latest != current

    def download_from_yandex_disk(self, url):
        """Скачать с Яндекс.Диска - УЛУЧШЕННАЯ ВЕРСИЯ"""
        try:
            temp_dir = tempfile.mkdtemp()
            # Сохраняем с правильным именем EXE
            file_path = os.path.join(temp_dir, self.exe_name)

            print(f"Скачивание с Яндекс.Диска: {url}")

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            response = requests.get(url, headers=headers, stream=True, timeout=60)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0

            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)

            # Проверяем, что файл скачан полностью
            if total_size > 0 and downloaded_size != total_size:
                return False, f"Файл скачан не полностью: {downloaded_size}/{total_size} байт"

            # Проверяем, что файл имеет минимальный размер (хотя бы 1MB)
            file_size = os.path.getsize(file_path)
            if file_size < 1024 * 1024:
                return False, f"Файл слишком мал: {file_size} байт"

            print(f"Файл успешно скачан: {file_path} ({file_size} байт)")
            return True, file_path

        except Exception as e:
            return False, f"Ошибка скачивания с Яндекс.Диска: {e}"

    def install_update(self, update_info):
        """Установить обновление с Яндекс.Диска - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        try:
            print("Начало установки обновления...")

            # Создаем резервную копию
            backup_made = self.create_backup()
            if not backup_made:
                print("Предупреждение: не удалось создать резервную копию")

            download_url = update_info.get("download_url")
            if not download_url:
                return False, "Не указана ссылка для скачивания"

            print("Скачивание обновления с Яндекс.Диска...")

            # Скачиваем файл
            success, result = self.download_from_yandex_disk(download_url)
            if not success:
                return False, result

            downloaded_file = result

            # Проверяем, что файл скачан
            if not os.path.exists(downloaded_file):
                return False, "Файл не был скачан"

            # Создаем BAT файл для установки - ИСПРАВЛЕННАЯ ВЕРСИЯ
            bat_content = f'''@echo off
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
    echo Проверьте права доступа к папке.
    pause
    exit /b 1
)

echo [6/7] Проверка нового EXE...
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

REM Очистка BAT файла
del /q "%~f0" >nul 2>&1
'''

            bat_path = os.path.join(self.script_dir, "apply_update.bat")
            with open(bat_path, "w", encoding="utf-8") as f:
                f.write(bat_content)

            # Обновляем версию в конфиге
            if update_info and update_info.get("version"):
                self._write_version(update_info["version"])

            print("Запуск BAT файла для применения обновления...")

            # Запускаем BAT файл с правами администратора
            try:
                subprocess.Popen([
                    'cmd', '/c', bat_path
                ], cwd=self.script_dir, shell=True)
            except Exception as e:
                print(f"Ошибка запуска BAT: {e}")
                # Пробуем альтернативный способ
                os.system(f'start "" "{bat_path}"')

            sys.exit(0)
            return True, "Запущена установка обновления"

        except Exception as e:
            return False, f"Ошибка установки обновления: {e}"

    def _write_version(self, version_str):
        """Записать версию в repo_config.json"""
        try:
            config_path = os.path.join(self.script_dir, "repo_config.json")
            data = self.config.copy()
            data["current_version"] = version_str.lstrip("vV")
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"Версия обновлена до {data['current_version']}")
            self.current_version = data["current_version"]
            self.config = data
        except Exception as e:
            print(f"Не удалось обновить repo_config.json: {e}")

    def create_backup(self):
        """Создать резервную копию"""
        try:
            backup_dir = os.path.join(self.script_dir, "backups")
            os.makedirs(backup_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = os.path.join(backup_dir, f"backup_{ts}")
            os.makedirs(dest, exist_ok=True)

            # Копируем важные файлы
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

            print(f"Резервная копия создана: {dest} ({copied} файлов)")
            return True
        except Exception as e:
            print(f"Ошибка создания резервной копии: {e}")
            return False

    def download_and_install_update(self, update_info):
        """Полный цикл обновления"""
        try:
            print("Начало процесса обновления...")
            return self.install_update(update_info)

        except Exception as e:
            return False, f"Ошибка обновления: {e}"

    def get_update_info(self):
        """Получить информацию о настройках обновлений"""
        return {
            "type": self.config.get("type", "yandex_disk"),
            "yandex_disk_url": self.config.get("yandex_disk_url", ""),
            "current_version": self.current_version
        }