# update_manager.py - ИСПРАВЛЕННАЯ ВЕРСИЯ С ПРАВИЛЬНЫМ СКАЧИВАНИЕМ
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
                     if f.endswith('.exe') and f.startswith('DocumentFiller')]

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
                    "type": "mail_ru_cloud",
                    "mail_ru_cloud_url": "",
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
        """Проверка обновлений"""
        try:
            mail_ru_url = self.config.get("mail_ru_cloud_url", "").strip()
            if not mail_ru_url:
                return False, "Не указана ссылка на папку в Облаке Mail.ru"

            print(f"🔍 Проверка обновлений в Облаке Mail.ru: {mail_ru_url}")

            # Получаем HTML страницу
            html_content = self.get_mail_ru_cloud_folder_html(mail_ru_url)
            if not html_content:
                return False, "Не удалось получить содержимое папки Облака Mail.ru"

            print(f"📄 Получено HTML содержимое, длина: {len(html_content)} симвонов")

            # Ищем все EXE файлы в HTML
            exe_files = self.find_exe_files_in_mail_ru_html(html_content, mail_ru_url)
            print(f"📁 Найдено EXE файлов: {len(exe_files)}")

            for file_name, file_url in exe_files:
                print(f"   - {file_name} -> {file_url}")

            if not exe_files:
                return False, "В папке не найдены EXE файлы"

            # Извлекаем версии из имен файлов
            version_files = []
            for file_name, file_url in exe_files:
                version = self.extract_version_from_filename(file_name)
                if version:
                    version_files.append({
                        'version': version,
                        'file_name': file_name,
                        'download_url': file_url
                    })
                    print(f"✅ Файл с версией: {file_name} -> версия {version}")

            if not version_files:
                return False, "Не найдены файлы с версиями в названии"

            # Находим самую новую версию
            latest_version_info = self.find_latest_version(version_files)

            if not latest_version_info:
                return False, "Не удалось определить последнюю версию"

            latest_version = latest_version_info['version']
            download_url = latest_version_info['download_url']

            print(f"📋 Самая новая версия: {latest_version}, текущая: {self.current_version}")

            if self.is_newer_version(latest_version, self.current_version):
                info = {
                    "version": latest_version,
                    "download_url": download_url,
                    "update_type": "mail_ru_cloud",
                    "release_notes": f"Доступна новая версия {latest_version}"
                }
                return True, info
            else:
                return True, "up_to_date"

        except Exception as e:
            return False, f"Ошибка проверки обновлений: {str(e)}"

    def get_mail_ru_cloud_folder_html(self, folder_url):
        """Получить HTML содержимое папки Облака Mail.ru"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }

            response = requests.get(folder_url, headers=headers, timeout=30)
            response.raise_for_status()

            return response.text
        except Exception as e:
            print(f"Ошибка получения HTML папки Облака Mail.ru: {e}")
            return None

    def find_exe_files_in_mail_ru_html(self, html_content, base_url):
        """Найти EXE файлы в HTML Облака Mail.ru - УЛУЧШЕННАЯ ВЕРСИЯ"""
        exe_files = []

        try:
            # Используем BeautifulSoup если установлен
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')

            # Ищем все ссылки на EXE файлы
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                if href and '.exe' in href.lower():
                    file_url = self.normalize_file_url(href, base_url)
                    file_name = os.path.basename(urllib.parse.urlparse(file_url).path)

                    if 'documentfiller' in file_name.lower():
                        exe_files.append((file_name, file_url))
                        print(f"✅ Найден EXE файл: {file_name} -> {file_url}")

        except ImportError:
            print("⚠️ BeautifulSoup не установлен, используем базовый парсинг")
            # Базовый парсинг regex
            patterns = [
                r'href="([^"]*\.exe[^"]*)"',
                r"href='([^']*\.exe[^']*)'",
            ]

            for pattern in patterns:
                matches = re.findall(pattern, html_content, re.IGNORECASE)
                for match in matches:
                    if 'documentfiller' in match.lower():
                        file_url = self.normalize_file_url(match, base_url)
                        file_name = os.path.basename(urllib.parse.urlparse(file_url).path)
                        exe_files.append((file_name, file_url))
                        print(f"✅ Найден EXE (regex): {file_name} -> {file_url}")

        # Убираем дубликаты
        unique_files = []
        seen_urls = set()

        for file_name, file_url in exe_files:
            if file_url not in seen_urls:
                unique_files.append((file_name, file_url))
                seen_urls.add(file_url)

        return unique_files

    def normalize_file_url(self, file_url, base_url):
        """Нормализовать URL файла"""
        try:
            # Если URL уже абсолютный, возвращаем как есть
            if file_url.startswith('http://') or file_url.startswith('https://'):
                return file_url

            # Если URL начинается с //
            if file_url.startswith('//'):
                return 'https:' + file_url

            # Если URL начинается с / (абсолютный путь на домене)
            if file_url.startswith('/'):
                return 'https://cloud.mail.ru' + file_url

            # Если URL относительный (начинается с ./ или просто имя файла)
            parsed_base = urllib.parse.urlparse(base_url)
            base_path = parsed_base.path

            # Убеждаемся, что base_path заканчивается на /
            if not base_path.endswith('/'):
                base_path += '/'

            # Убираем ./ из начала если есть
            if file_url.startswith('./'):
                file_url = file_url[2:]

            # Собираем полный URL
            full_url = f"https://{parsed_base.netloc}{base_path}{file_url}"

            print(f"🔗 Нормализован URL: {file_url} -> {full_url}")
            return full_url

        except Exception as e:
            print(f"❌ Ошибка нормализации URL {file_url}: {e}")
            return file_url

    def extract_version_from_filename(self, filename):
        """Извлечь версию из имени файла"""
        try:
            patterns = [
                r'DocumentFiller[_-]v?(\d+\.\d+\.\d+)\.exe',
                r'DocumentFiller[_-]v?(\d+\.\d+)\.exe',
                r'DocumentFiller[_-]v?(\d+)\.exe',
                r'v?(\d+\.\d+\.\d+)\.exe',
                r'v?(\d+\.\d+)\.exe',
                r'v?(\d+)\.exe'
            ]

            for pattern in patterns:
                match = re.search(pattern, filename, re.IGNORECASE)
                if match:
                    return match.group(1)

            return None
        except:
            return None

    def find_latest_version(self, version_files):
        """Найти самую новую версию из списка"""
        if not version_files:
            return None

        latest = version_files[0]

        for file_info in version_files[1:]:
            if self.is_newer_version(file_info['version'], latest['version']):
                latest = file_info

        return latest

    def is_newer_version(self, latest, current):
        """Сравнение версий"""
        try:
            def parse_version(version_str):
                parts = []
                for part in version_str.split('.'):
                    if part.isdigit():
                        parts.append(int(part))
                    else:
                        parts.append(0)
                return parts

            latest_parts = parse_version(latest)
            current_parts = parse_version(current)

            for i in range(max(len(latest_parts), len(current_parts))):
                lv = latest_parts[i] if i < len(latest_parts) else 0
                cv = current_parts[i] if i < len(current_parts) else 0
                if lv > cv:
                    return True
                if lv < cv:
                    return False
            return False
        except:
            return latest != current

    def download_from_mail_ru_cloud(self, url):
        """Скачать из Облака Mail.ru - ПОЛНОСТЬЮ ПЕРЕРАБОТАННАЯ ВЕРСИЯ"""
        try:
            temp_dir = tempfile.mkdtemp()
            file_name = os.path.basename(urllib.parse.urlparse(url).path)
            file_path = os.path.join(temp_dir, file_name)

            print(f"📥 Скачивание обновления: {url}")
            print(f"📁 Временный путь: {file_path}")

            # Создаем сессию для сохранения cookies
            session = requests.Session()

            # Улучшенные заголовки для имитации браузера
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Cache-Control': 'max-age=0',
                'Referer': 'https://cloud.mail.ru/'
            }

            print("🔍 Отправка запроса...")

            # Отправляем запрос с обработкой редиректов
            response = session.get(url, headers=headers, stream=True, timeout=60, allow_redirects=True)
            response.raise_for_status()

            # Проверяем content-type
            content_type = response.headers.get('content-type', '').lower()
            print(f"📄 Content-Type: {content_type}")

            # Проверяем, что это не HTML страница
            if 'text/html' in content_type:
                # Сохраняем HTML для отладки
                debug_path = file_path + '.html'
                with open(debug_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                print(f"⚠️ Скачана HTML страница вместо EXE. Сохранено в: {debug_path}")

                # Попробуем найти прямую ссылку на скачивание в HTML
                html_content = response.text
                direct_links = re.findall(r'https?://[^"\']*\.exe[^"\']*', html_content)

                if direct_links:
                    print(f"🔍 Найдены прямые ссылки в HTML: {direct_links}")
                    # Попробуем первую найденную ссылку
                    direct_url = direct_links[0]
                    print(f"🔄 Пробуем скачать по прямой ссылке: {direct_url}")
                    return self.download_from_mail_ru_cloud(direct_url)
                else:
                    return False, "Скачана HTML страница вместо EXE файла. Возможно, требуется авторизация."

            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0

            print(f"💾 Размер файла: {total_size} байт")

            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)

                        if total_size > 0:
                            percent = (downloaded_size / total_size) * 100
                            print(f"📥 Прогресс: {percent:.1f}% ({downloaded_size}/{total_size} байт)", end='\r')

            print()

            # Проверяем размер файла
            file_size = os.path.getsize(file_path)
            print(f"📊 Фактический размер файла: {file_size} байт")

            if file_size < 2 * 1024 * 1024:  # Минимум 2 МБ для EXE
                # Проверяем, не HTML ли это
                with open(file_path, 'rb') as f:
                    first_bytes = f.read(100)
                    if b'<html' in first_bytes.lower() or b'<!doctype' in first_bytes.lower():
                        return False, f"Скачан HTML файл вместо EXE. Размер: {file_size} байт"

                return False, f"Файл слишком мал для EXE: {file_size} байт (ожидается >2 МБ)"

            print(f"✅ Файл успешно скачан: {file_path} ({file_size} байт)")
            return True, file_path

        except Exception as e:
            return False, f"Ошибка скачивания: {e}"

    def install_update(self, update_info):
        """Установить обновление"""
        try:
            print("🔄 Начало установки обновления...")

            backup_made = self.create_backup()
            if not backup_made:
                print("⚠️ Предупреждение: не удалось создать резервную копию")

            download_url = update_info.get("download_url")
            if not download_url:
                return False, "Не указана ссылка для скачивания"

            print("📥 Скачивание обновления из Облака Mail.ru...")

            success, result = self.download_from_mail_ru_cloud(download_url)
            if not success:
                return False, result

            downloaded_file = result

            if not os.path.exists(downloaded_file):
                return False, "Файл не был скачан"

            # Проверяем, что файл действительно EXE
            if not self.is_valid_exe_file(downloaded_file):
                return False, "Скачанный файл не является корректным EXE файлом"

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

    def get_update_info(self):
        """Получить информацию о настройках обновлений"""
        return {
            "type": self.config.get("type", "mail_ru_cloud"),
            "mail_ru_cloud_url": self.config.get("mail_ru_cloud_url", ""),
            "current_version": self.current_version
        }