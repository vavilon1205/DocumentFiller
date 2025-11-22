# update_manager.py
# Улучшённый менеджер обновлений для DocumentFiller.exe
# Поддерживает безопасное обновление EXE через временный bat (Windows).
# Работает в режиме frozen (собранный exe) и в режиме скрипта.

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
        # Папка для временных операций внутри директории приложения
        self.local_tmp = os.path.join(self.script_dir, "__update_tmp")
        os.makedirs(self.local_tmp, exist_ok=True)

    def get_script_dir(self):
        """Возвращает директорию приложения (где лежит exe или скрипт)."""
        if getattr(sys, "frozen", False):
            return os.path.dirname(sys.executable)
        else:
            return os.path.dirname(os.path.abspath(__file__))

    def load_config(self):
        """Загрузить repo_config.json (если нет — создать дефолт)."""
        try:
            config_path = os.path.join(self.script_dir, "repo_config.json")
            if not os.path.exists(config_path):
                default_config = {
                    "type": "github",
                    "owner": "",
                    "repo": "",
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
        """Чтение текущей версии из version_config.json (или создание дефолтной)."""
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
        """Проверяет GitHub Releases и возвращает (True, update_info) если доступно обновление,
           или (True, "up_to_date") если нет, или (False, error_message)."""
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
            if resp.status_code == 404:
                return False, "Репозиторий или релиз не найден"
            if resp.status_code == 403:
                return False, "Превышен лимит запросов GitHub"
            if resp.status_code != 200:
                return False, f"Ошибка GitHub API: {resp.status_code}"

            rd = resp.json()
            latest_tag = rd.get("tag_name") or rd.get("name")
            if not latest_tag:
                return False, "Не удалось определить версию в релизе"

            latest = latest_tag.lstrip("vV")
            if self.is_newer_version(latest, self.current_version):
                download_url = rd.get("zipball_url") or rd.get("tarball_url")
                info = {
                    "version": latest,
                    "download_url": download_url,
                    "release_notes": rd.get("body", ""),
                    "published_at": rd.get("published_at", "")
                }
                return True, info
            else:
                return True, "up_to_date"

        except requests.exceptions.Timeout:
            return False, "Таймаут при проверке обновлений"
        except requests.exceptions.ConnectionError:
            return False, "Ошибка подключения к интернету"
        except Exception as e:
            return False, f"Ошибка при проверке обновлений: {e}"

    def is_newer_version(self, latest, current):
        """Сравнение семантических версий (простое)"""
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
        """Скачать обновление в временную папку приложения."""
        try:
            if not download_url:
                return False, "URL для скачивания не указан"

            tmp = tempfile.mkdtemp()
            zip_path = os.path.join(tmp, "update.zip")

            headers = {"User-Agent": "DocumentFiller-Updater/1.0"}
            token = self.config.get("token", "").strip()
            if token and "api.github.com" in download_url:
                headers["Authorization"] = f"token {token}"

            with requests.get(download_url, headers=headers, stream=True, timeout=30) as r:
                r.raise_for_status()
                with open(zip_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

            return True, zip_path
        except Exception as e:
            return False, f"Ошибка скачивания: {e}"

    def install_update(self, zip_path, update_info):
        """Установить обновление из zip_path. update_info должен содержать 'version'."""
        backup_made = False
        try:
            # 1) Создать резервную копию
            backup_made = self.create_backup()

            # 2) Распаковать zip в временную папку
            extract_dir = tempfile.mkdtemp()
            with zipfile.ZipFile(zip_path, "r") as z:
                z.extractall(extract_dir)

            # 3) Найти папку с содержимым релиза (обычно первая папка)
            entries = [p for p in os.listdir(extract_dir) if os.path.isdir(os.path.join(extract_dir, p))]
            if not entries:
                return False, "Архив обновления не содержит файлов"

            update_root = os.path.join(extract_dir, entries[0])

            # Иногда в релизе есть лишняя вложенность — спускаемся, если очевидно
            while True:
                subdirs = [d for d in os.listdir(update_root) if os.path.isdir(os.path.join(update_root, d))]
                # Если одна папка и в ней нет файлов проекта — углубляемся
                if len(subdirs) == 1 and not any(name.lower().endswith(".py") or name.lower().endswith(".exe") for name in os.listdir(update_root)):
                    update_root = os.path.join(update_root, subdirs[0])
                else:
                    break

            # 4) Скопировать файлы в локальную временную папку внутри приложения (чтобы bat мог их применить)
            # Удаляем предыдущую локальную tmp, если есть
            try:
                if os.path.exists(self.local_tmp):
                    shutil.rmtree(self.local_tmp)
                shutil.copytree(update_root, self.local_tmp)
            except Exception as e:
                # fallback: копировать по файлам
                os.makedirs(self.local_tmp, exist_ok=True)
                for root, dirs, files in os.walk(update_root):
                    rel = os.path.relpath(root, update_root)
                    dst_dir = os.path.join(self.local_tmp, rel) if rel != "." else self.local_tmp
                    os.makedirs(dst_dir, exist_ok=True)
                    for f in files:
                        shutil.copy2(os.path.join(root, f), os.path.join(dst_dir, f))

            # 5) Если запущены как собранный exe — сделать bat-обновление
            if getattr(sys, "frozen", False):
                # Создать run_updater.bat в папке приложения
                bat_path = os.path.join(self.script_dir, "run_updater.bat")
                # Используем robocopy для надежного копирования (robocopy есть в Windows)
                # bat: дождаться закрытия процесса, затем зеркально скопировать из __update_tmp в app dir, запустить exe, удалить временные файлы и сам bat
                bat_content = f"""@echo off
REM Небольшая пауза — даем основному процессу завершиться
timeout /t 2 /nobreak >nul
REM Пробуем принудительно завершить процесс на случай, если он ещё удерживает файлы
taskkill /f /im "{self.exe_name}" >nul 2>&1
REM Копируем (зеркально) обновлённые файлы в папку приложения
robocopy "%~dp0__update_tmp" "%~dp0" /MIR /NFL /NDL /NJH /NJS /R:3 /W:2
REM Запускаем приложение (если exe есть)
if exist "%~dp0{self.exe_name}" (
    start "" "%~dp0{self.exe_name}"
)
REM Удаляем временную папку
rmdir /s /q "%~dp0__update_tmp"
REM Удаляем сам bat
del /q "%~f0"
"""
                with open(bat_path, "w", encoding="utf-8") as f:
                    f.write(bat_content)

                # Запускаем bat и завершаем текущий процесс, чтобы bat мог заменить exe
                # Используем creationflags=subprocess.CREATE_NEW_CONSOLE чтобы bat мог выполняться независимо
                try:
                    subprocess.Popen([bat_path], cwd=self.script_dir, shell=True)
                except Exception:
                    # fallback: запуск через cmd
                    subprocess.Popen(["cmd", "/c", bat_path], cwd=self.script_dir)
                # Обновление будет выполнено внешним bat — завершаем текущий процесс
                sys.exit(0)

            else:
                # Запущено как скрипт — можно копировать прямо сейчас
                self.copy_update_files(self.local_tmp, self.script_dir)

                # Обновляем version_config.json на новую версию
                if update_info and update_info.get("version"):
                    self._write_version(update_info["version"])

                # Перезапускаем скрипт (python main.py)
                try:
                    python = sys.executable
                    main_script = os.path.join(self.script_dir, "main.py")
                    subprocess.Popen([python, main_script], cwd=self.script_dir)
                    sys.exit(0)
                except Exception as e:
                    return True, "Обновление установлено, но не удалось перезапустить приложение: " + str(e)

            # Если пришли сюда — значит bat будет заниматься остальным
            # Запишем версию в config (чтобы при старте новая версия считалась актуальной)
            if update_info and update_info.get("version"):
                self._write_version(update_info["version"])

            return True, "Обновление установлено (через внешний апдейтер)"
        except Exception as e:
            # В случае ошибки — пытаемся восстановить
            if backup_made:
                self.restore_backup()
            return False, f"Ошибка установки обновления: {e}"
        finally:
            # очищаем загруженный zip и временную распаковку
            try:
                if os.path.exists(zip_path):
                    os.remove(zip_path)
            except:
                pass

    def copy_update_files(self, source_dir, target_dir):
        """Копирует файлы обновления в целевую папку, сохраняя пользовательские файлы."""
        exclude = {
            "backups",
            "Шаблоны",
            "анкеты_данные.xlsx",
            "license.json",
            "repo_config.json",
            "version_config.json",
            "settings.ini",
            "update.log",
            "__pycache__",
            ".git"
        }

        for root, dirs, files in os.walk(source_dir):
            rel = os.path.relpath(root, source_dir)
            dest_root = os.path.join(target_dir, rel) if rel != "." else target_dir

            # Создаём папку назначения если не существует
            os.makedirs(dest_root, exist_ok=True)

            # Список папок для прохода: исключаем папки-исключения
            dirs[:] = [d for d in dirs if d not in exclude]

            for f in files:
                if f in exclude:
                    continue
                src_file = os.path.join(root, f)
                dst_file = os.path.join(dest_root, f)
                try:
                    # Если файл существует и это важный пользовательский файл — пропускаем перезапись
                    if os.path.exists(dst_file):
                        # Не перезаписываем пользовательские файлы из exclude
                        if os.path.basename(dst_file) in ("анкеты_данные.xlsx", "license.json", "settings.ini"):
                            # пропускаем
                            print(f"Пропуск пользовательского файла: {dst_file}")
                            continue
                        # Иначе удалим и запишем новую версию
                        try:
                            if os.path.isdir(dst_file):
                                shutil.rmtree(dst_file)
                            else:
                                os.remove(dst_file)
                        except Exception:
                            pass
                    shutil.copy2(src_file, dst_file)
                    print(f"Скопирован {dst_file}")
                except Exception as e:
                    print(f"Ошибка копирования {src_file} -> {dst_file}: {e}")

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
        """Создать резервную копию важных файлов перед обновлением."""
        try:
            backup_dir = os.path.join(self.script_dir, "backups")
            os.makedirs(backup_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = os.path.join(backup_dir, f"backup_{ts}")
            os.makedirs(dest, exist_ok=True)
            important = [
                "main.py", "main_window.py", "settings.py", "theme_manager.py",
                "widgets.py", "update_manager.py", "license_manager.py",
                "version_config.json", "repo_config.json", "анкеты_данные.xlsx",
                "license.json", self.exe_name
            ]
            copied = 0
            for name in important:
                src = os.path.join(self.script_dir, name)
                if os.path.exists(src):
                    try:
                        if os.path.isdir(src):
                            shutil.copytree(src, os.path.join(dest, name))
                        else:
                            shutil.copy2(src, os.path.join(dest, name))
                        copied += 1
                    except Exception:
                        pass
            print(f"Резервная копия создана: {dest} ({copied} файлов/папок)")
            return True
        except Exception as e:
            print(f"Ошибка создания резервной копии: {e}")
            return False

    def restore_backup(self):
        """Восстановление из последней резервной копии."""
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
            return True, f"Восстановлено {restored}"
        except Exception as e:
            return False, f"Ошибка восстановления: {e}"

    def download_and_install_update(self, update_info):
        """Управляет полным циклом: download -> install"""
        try:
            ok, result = self.download_update(update_info.get("download_url"))
            if not ok:
                return False, result
            zip_path = result
            return self.install_update(zip_path, update_info)
        except Exception as e:
            return False, f"Ошибка обновления: {e}"

    def get_repository_info(self):
        return {
            "configured": self.is_repository_configured(),
            "owner": self.config.get("owner", ""),
            "repo": self.config.get("repo", ""),
            "branch": self.config.get("branch", "main")
        }

# Пример использования:
# if __name__ == "__main__":
#     um = UpdateManager(exe_name="DocumentFiller.exe")
#     ok, res = um.check_for_updates()
#     if ok and res != "up_to_date":
#         print("Есть обновление:", res["version"])
#         ok2, msg = um.download_and_install_update(res)
#         print(ok2, msg)
#     else:
#         print("Обновлений нет или ошибка:", res)
