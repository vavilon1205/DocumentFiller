# update_manager.py - ВЕРСИЯ БЕЗ СБОРКИ EXE НА СТОРОНЕ КЛИЕНТА
import os
import sys
import json
import shutil
import tempfile
import zipfile
import requests
import subprocess
from pathlib import Path
from datetime import datetime


class UpdateManager:
    def __init__(self, exe_name="DocumentFiller.exe"):
        self.exe_name = exe_name
        self.script_dir = self.get_script_dir()
        self.config = self.load_config()
        self.current_version = self.get_current_version()
        self.local_tmp = os.path.join(self.script_dir, "__update_tmp")
        os.makedirs(self.local_tmp, exist_ok=True)

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
                    "owner": "vavilon1205",
                    "repo": "DocumentFiller",
                    "branch": "main",
                    "token": "",
                    "update_channel": "stable"
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
        """Чтение текущей версии"""
        try:
            version_path = os.path.join(self.script_dir, "version_config.json")
            if not os.path.exists(version_path):
                default_ver = {
                    "current_version": "1.0.0",
                    "update_url": "",
                    "check_updates_on_start": False,
                    "update_channel": "stable"
                }
                with open(version_path, "w", encoding="utf-8") as f:
                    json.dump(default_ver, f, indent=2, ensure_ascii=False)
                return default_ver["current_version"]

            with open(version_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("current_version", "1.0.0")
        except Exception as e:
            print(f"Ошибка чтения версии: {e}")
            return "1.0.0"

    def is_repository_configured(self):
        return bool(self.config.get("owner") and self.config.get("repo"))

    def check_for_updates(self):
        """Проверяет обновления - ИЩЕТ EXE В ASSETS"""
        try:
            if not self.is_repository_configured():
                return False, "Репозиторий не настроен"

            owner = self.config.get("owner")
            repo = self.config.get("repo")
            token = self.config.get("token", "").strip()

            url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
            headers = {"User-Agent": "DocumentFiller-Updater/1.0"}
            if token:
                headers["Authorization"] = f"token {token}"

            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                return False, f"Ошибка GitHub API: {resp.status_code}"

            rd = resp.json()
            latest_tag = rd.get("tag_name") or rd.get("name")
            if not latest_tag:
                return False, "Не удалось определить версию в релизе"

            latest = latest_tag.lstrip("vV")

            # Проверяем, есть ли новая версия
            if not self.is_newer_version(latest, self.current_version):
                return True, "up_to_date"

            # Ищем EXE файл в assets
            assets = rd.get("assets", [])
            exe_asset = None
            zip_asset = None

            for asset in assets:
                name = asset.get("name", "").lower()
                if name == "documentfiller.exe":
                    exe_asset = asset
                elif name == "documentfiller.zip":
                    zip_asset = asset

            # Предпочитаем EXE, но если нет - используем ZIP
            download_url = None
            if exe_asset:
                download_url = exe_asset.get("browser_download_url")
                asset_type = "exe"
            elif zip_asset:
                download_url = zip_asset.get("browser_download_url")
                asset_type = "zip"
            else:
                # Если нет готовых билдов, используем исходники (но это запасной вариант)
                download_url = rd.get("zipball_url")
                asset_type = "source"

            info = {
                "version": latest,
                "download_url": download_url,
                "asset_type": asset_type,
                "release_notes": rd.get("body", ""),
                "published_at": rd.get("published_at", "")
            }
            return True, info

        except Exception as e:
            return False, f"Ошибка при проверке обновлений: {e}"

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

    def download_update(self, download_url):
        """Скачать обновление"""
        try:
            if not download_url:
                return False, "URL для скачивания не указан"

            tmp = tempfile.mkdtemp()

            # Определяем расширение файла из URL
            if download_url.endswith('.exe'):
                file_ext = '.exe'
            elif download_url.endswith('.zip'):
                file_ext = '.zip'
            else:
                file_ext = '.zip'  # по умолчанию

            zip_path = os.path.join(tmp, f"update_{datetime.now().strftime('%Y%m%d_%H%M%S')}{file_ext}")

            headers = {"User-Agent": "DocumentFiller-Updater/1.0"}
            token = self.config.get("token", "").strip()
            if token and "api.github.com" in download_url:
                headers["Authorization"] = f"token {token}"

            print(f"Скачивание обновления с: {download_url}")
            with requests.get(download_url, headers=headers, stream=True, timeout=30) as r:
                r.raise_for_status()
                with open(zip_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

            return True, zip_path
        except Exception as e:
            return False, f"Ошибка скачивания: {e}"

    def install_update(self, update_path, update_info):
        """Установить обновление - ТОЛЬКО ГОТОВЫЕ БИЛДЫ"""
        try:
            print(f"Начало установки обновления из: {update_path}")

            # Создаем резервную копию
            backup_made = self.create_backup()
            if not backup_made:
                print("Предупреждение: не удалось создать резервную копию")

            asset_type = update_info.get("asset_type", "zip")

            if asset_type == "exe":
                return self.install_exe_update(update_path, update_info)
            elif asset_type == "zip":
                return self.install_zip_update(update_path, update_info)
            else:
                return False, "Тип обновления не поддерживается. Нужен EXE или ZIP файл."

        except Exception as e:
            error_msg = f"Ошибка установки обновления: {e}"
            print(error_msg)
            if backup_made:
                self.restore_backup()
            return False, error_msg

    def install_exe_update(self, exe_path, update_info):
        """Установка через EXE файл"""
        try:
            print("Установка через EXE файл...")

            # Создаем bat файл для установки
            bat_content = f'''@echo off
chcp 65001 >nul
title Обновление DocumentFiller
echo =======================================
echo    Установка обновления DocumentFiller
echo =======================================
echo.

echo [1/5] Ожидание завершения текущей программы...
timeout /t 3 /nobreak >nul

echo [2/5] Завершение процесса {self.exe_name}...
taskkill /f /im "{self.exe_name}" >nul 2>&1

echo [3/5] Ожидание освобождения файлов...
timeout /t 2 /nobreak >nul

echo [4/5] Замена EXE файла...
copy /Y "{exe_path}" "{os.path.join(self.script_dir, self.exe_name)}" >nul

echo [5/5] Запуск обновленной программы...
cd /d "{self.script_dir}"
start "" "{os.path.join(self.script_dir, self.exe_name)}"

echo Обновление успешно завершено!
timeout /t 2 >nul

REM Очистка
del /q "{exe_path}" >nul 2>&1
del /q "%~f0" >nul 2>&1
'''

            bat_path = os.path.join(self.script_dir, "update_exe.bat")
            with open(bat_path, "w", encoding="utf-8") as f:
                f.write(bat_content)

            # Обновляем версию в конфиге
            if update_info and update_info.get("version"):
                self._write_version(update_info["version"])

            print("Запуск BAT файла для применения обновления...")
            subprocess.Popen([bat_path], cwd=self.script_dir, shell=True)
            sys.exit(0)

            return True, "Запущена установка EXE обновления"

        except Exception as e:
            return False, f"Ошибка установки через EXE: {e}"

    def install_zip_update(self, zip_path, update_info):
        """Установка через ZIP архив с готовым билдом"""
        try:
            print("Установка через ZIP архив с готовым билдом...")

            # Распаковываем архив
            extract_dir = tempfile.mkdtemp()
            print(f"Распаковка в: {extract_dir}")
            with zipfile.ZipFile(zip_path, "r") as z:
                z.extractall(extract_dir)

            # Ищем EXE файл в распакованных файлах
            exe_files = []
            for root, dirs, files in os.walk(extract_dir):
                for file in files:
                    if file.lower() == self.exe_name.lower():
                        exe_files.append(os.path.join(root, file))

            if not exe_files:
                return False, "EXE файл не найден в архиве"

            exe_path = exe_files[0]
            print(f"Найден EXE файл: {exe_path}")

            # Создаем bat файл для установки
            bat_content = f'''@echo off
chcp 65001 >nul
title Обновление DocumentFiller
echo =======================================
echo    Установка обновления DocumentFiller
echo =======================================
echo.

echo [1/6] Ожидание завершения текущей программы...
timeout /t 3 /nobreak >nul

echo [2/6] Завершение процесса {self.exe_name}...
taskkill /f /im "{self.exe_name}" >nul 2>&1

echo [3/6] Ожидание освобождения файлов...
timeout /t 2 /nobreak >nul

echo [4/6] Копирование обновленных файлов...
REM Копируем все файлы из архива
xcopy "{extract_dir}\\*" "{self.script_dir}\\" /Y /E /H /I >nul 2>&1

echo [5/6] Очистка временных файлов...
rmdir /s /q "{extract_dir}" >nul 2>&1
del /q "{zip_path}" >nul 2>&1

echo [6/6] Запуск обновленной программы...
cd /d "{self.script_dir}"
start "" "{os.path.join(self.script_dir, self.exe_name)}"

echo Обновление успешно завершено!
timeout /t 2 >nul
del /q "%~f0" >nul 2>&1
'''

            bat_path = os.path.join(self.script_dir, "update_zip.bat")
            with open(bat_path, "w", encoding="utf-8") as f:
                f.write(bat_content)

            # Обновляем версию в конфиге
            if update_info and update_info.get("version"):
                self._write_version(update_info["version"])

            print("Запуск BAT файла для применения обновления...")
            subprocess.Popen([bat_path], cwd=self.script_dir, shell=True)
            sys.exit(0)

            return True, "Запущена установка ZIP обновления"

        except Exception as e:
            return False, f"Ошибка установки через ZIP: {e}"

    def _write_version(self, version_str):
        """Записать версию в version_config.json"""
        try:
            vp = os.path.join(self.script_dir, "version_config.json")
            data = {}
            if os.path.exists(vp):
                with open(vp, "r", encoding="utf-8") as f:
                    data = json.load(f)
            data["current_version"] = version_str.lstrip("vV")
            with open(vp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"Версия обновлена до {data['current_version']}")
            self.current_version = data["current_version"]
        except Exception as e:
            print(f"Не удалось обновить version_config.json: {e}")

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
                "main.py", "main_window.py", "settings.py", "theme_manager.py",
                "widgets.py", "update_manager.py", "license_manager.py",
                "version_config.json", "repo_config.json", "анкеты_данные.xlsx",
                "license.json", self.exe_name
            ]

            copied = 0
            for name in important_files:
                src = os.path.join(self.script_dir, name)
                if os.path.exists(src):
                    try:
                        if os.path.isdir(src):
                            shutil.copytree(src, os.path.join(dest, name))
                        else:
                            shutil.copy2(src, os.path.join(dest, name))
                        copied += 1
                    except Exception as e:
                        print(f"Ошибка копирования {name}: {e}")

            print(f"Резервная копия создана: {dest} ({copied} файлов)")
            return True
        except Exception as e:
            print(f"Ошибка создания резервной копии: {e}")
            return False

    def restore_backup(self):
        """Восстановление из резервной копии"""
        try:
            backup_dir = os.path.join(self.script_dir, "backups")
            if not os.path.exists(backup_dir):
                return False, "Папка backups не найдена"

            backups = [d for d in os.listdir(backup_dir) if d.startswith("backup_")]
            if not backups:
                return False, "Резервные копии не найдены"

            latest = sorted(backups)[-1]
            path = os.path.join(backup_dir, latest)

            restored = 0
            for item in os.listdir(path):
                src = os.path.join(path, item)
                dst = os.path.join(self.script_dir, item)
                try:
                    if os.path.exists(dst):
                        if os.path.isdir(dst):
                            shutil.rmtree(dst)
                        else:
                            os.remove(dst)
                    if os.path.isdir(src):
                        shutil.copytree(src, dst)
                    else:
                        shutil.copy2(src, dst)
                    restored += 1
                except Exception as e:
                    print(f"Ошибка восстановления {item}: {e}")

            print(f"Восстановлено {restored} файлов из {latest}")
            return True, f"Восстановлено {restored} файлов"
        except Exception as e:
            return False, f"Ошибка восстановления: {e}"

    def download_and_install_update(self, update_info):
        """Полный цикл обновления"""
        try:
            print("Начало процесса обновления...")

            ok, result = self.download_update(update_info.get("download_url"))
            if not ok:
                return False, result

            update_path = result
            return self.install_update(update_path, update_info)

        except Exception as e:
            return False, f"Ошибка обновления: {e}"

    def get_repository_info(self):
        return {
            "configured": self.is_repository_configured(),
            "owner": self.config.get("owner", ""),
            "repo": self.config.get("repo", ""),
            "branch": self.config.get("branch", "main")
        }

    def restart_program(self):
        """Перезапуск программы"""
        try:
            if getattr(sys, "frozen", False):
                exe_path = os.path.join(self.script_dir, self.exe_name)
                if os.path.exists(exe_path):
                    subprocess.Popen([exe_path], cwd=self.script_dir)
                    sys.exit(0)
            else:
                python = sys.executable
                main_script = os.path.join(self.script_dir, "main.py")
                subprocess.Popen([python, main_script], cwd=self.script_dir)
                sys.exit(0)
        except Exception as e:
            print(f"Ошибка перезапуска: {e}")