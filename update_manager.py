# update_manager.py - ДОБАВЛЕН FALLBACK ДЛЯ СЛУЧАЕВ, КОГДА АССЕТЫ НЕ НАЙДЕНЫ
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

                # Ищем EXE файл в ассетах
                exe_asset = None
                zip_asset = None
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

                # Сначала ищем EXE файлы
                for pattern in search_patterns:
                    for asset in assets:
                        if pattern(asset['name'].lower()):
                            exe_asset = asset
                            print(f"✅ Найден подходящий EXE: {asset['name']}")
                            break
                    if exe_asset:
                        break

                # Если EXE не найден, ищем ZIP архив
                if not exe_asset:
                    print("🔍 EXE файл не найден, ищем ZIP архив...")
                    zip_search_patterns = [
                        lambda name: name.endswith('.zip') and 'documentfiller' in name.lower(),
                        lambda name: name.endswith('.zip') and 'document' in name.lower(),
                        lambda name: name.endswith('.zip') and 'filler' in name.lower(),
                        lambda name: name.endswith('.zip')  # Любой ZIP файл
                    ]

                    for pattern in zip_search_patterns:
                        for asset in assets:
                            if pattern(asset['name'].lower()):
                                zip_asset = asset
                                print(f"✅ Найден ZIP архив: {asset['name']}")
                                break
                        if zip_asset:
                            break

                # Если найдены ассеты через API
                if exe_asset:
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
                elif zip_asset:
                    # Скачиваем и извлекаем EXE из ZIP
                    return self.handle_zip_update(zip_asset, latest_version)
                else:
                    # Ассеты не найдены через API, пробуем fallback-метод
                    print("🔍 Ассеты не найдены через API, пробуем fallback-метод...")
                    return self.try_fallback_download(owner, repo, tag_name, latest_version)

            else:
                print(f"ℹ️ Установлена последняя версия: {self.current_version}")
                return True, "up_to_date"

        except requests.exceptions.RequestException as e:
            return False, f"Ошибка сети: {str(e)}"
        except Exception as e:
            return False, f"Ошибка проверки обновлений GitHub: {str(e)}"

    def try_fallback_download(self, owner, repo, tag_name, latest_version):
        """Попробовать скачать обновление через прямые ссылки (fallback)"""
        try:
            print("🔄 Используем fallback-метод для поиска обновления...")

            # Генерируем возможные имена файлов
            possible_filenames = [
                f"DocumentFiller_v{latest_version}.exe",
                f"DocumentFiller_{tag_name}.exe",
                "DocumentFiller.exe",
                f"DocumentFiller_v{latest_version}.zip",
                f"DocumentFiller_{tag_name}.zip",
                "DocumentFiller.zip"
            ]

            # Пробуем каждый возможный файл
            for filename in possible_filenames:
                download_url = f"https://github.com/{owner}/{repo}/releases/download/{tag_name}/{filename}"
                print(f"🔗 Проверяем URL: {download_url}")

                # Проверяем доступность файла
                if self.check_url_exists(download_url):
                    print(f"✅ Файл найден: {filename}")

                    if filename.endswith('.exe'):
                        info = {
                            "version": latest_version,
                            "download_url": download_url,
                            "release_notes": f"Обновление до версии {latest_version}",
                            "release_name": f"DocumentFiller v{latest_version}",
                            "update_type": "github_fallback",
                            "asset_name": filename,
                            "tag_name": tag_name
                        }
                        return True, info
                    else:
                        # ZIP файл
                        zip_asset = {
                            'browser_download_url': download_url,
                            'name': filename
                        }
                        return self.handle_zip_update(zip_asset, latest_version)

            return False, "Не удалось найти файлы для обновления (ни через API, ни через прямые ссылки)"

        except Exception as e:
            return False, f"Ошибка fallback-метода: {str(e)}"

    def check_url_exists(self, url):
        """Проверить существование URL"""
        try:
            response = requests.head(url, timeout=5)
            return response.status_code == 200
        except:
            return False

    # Остальные методы остаются без изменений...
    # [extract_version_from_tag, handle_zip_update, download_from_github, extract_exe_from_zip,
    #  install_update, is_valid_exe_file, create_update_bat_script, create_backup,
    #  download_and_install_update, is_newer_version, normalize_version, get_update_info]