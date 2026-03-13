# update_manager.py — УДОБНОЕ авто- + ручное обновление (GitHub Releases, onedir-структура)

import os
import sys
import json
import requests
import shutil
import tempfile
import subprocess
import re
import zipfile
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Tuple

from PyQt5.QtWidgets import QMessageBox, QProgressDialog, QAction
from PyQt5.QtCore import QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QIcon


class UpdateWorker(QThread):
    progress = pyqtSignal(int)
    message = pyqtSignal(str)
    finished = pyqtSignal(bool, str, str)  # success, version or error, download_url если нужно

    def __init__(self, repo: str, current_version: str, silent: bool = False):
        super().__init__()
        self.repo = repo
        self.current_version = current_version
        self.silent = silent

    def run(self):
        try:
            api_url = f"https://api.github.com/repos/{self.repo}/releases/latest"
            headers = {"Accept": "application/vnd.github.v3+json"}
            r = requests.get(api_url, timeout=10, headers=headers)
            r.raise_for_status()
            data = r.json()

            tag = data["tag_name"].lstrip("vV ")
            release_version = self._clean_version(tag)

            if not self._is_newer(release_version, self.current_version):
                if not self.silent:
                    self.finished.emit(False, "У вас уже последняя версия", "")
                else:
                    self.finished.emit(False, "", "")
                return

            # Ищем подходящий zip
            asset_url = None
            asset_name = None
            expected_patterns = [
                f"DocumentFiller-{tag}.zip",
                f"DocumentFiller_{tag}.zip",
                f"DocumentFiller-v{tag}.zip",
                "DocumentFiller.zip"  # fallback — последний zip
            ]

            for asset in data.get("assets", []):
                name = asset["name"].lower()
                if any(pat.lower() in name for pat in expected_patterns) and name.endswith(".zip"):
                    asset_url = asset["browser_download_url"]
                    asset_name = asset["name"]
                    break

            if not asset_url:
                self.finished.emit(False, f"Не найден .zip в релизе {tag}", "")
                return

            self.message.emit(f"Найдена версия {tag}. Скачивание...")

            # Скачивание
            temp_dir = tempfile.mkdtemp(prefix="docfiller_upd_")
            zip_path = os.path.join(temp_dir, asset_name or "update.zip")

            with requests.get(asset_url, stream=True, timeout=30) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("content-length", 0))
                downloaded = 0
                with open(zip_path, "wb") as f:
                    for chunk in resp.iter_content(16384):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total > 0:
                                self.progress.emit(int(100 * downloaded / total))

            self.progress.emit(100)
            self.message.emit("Скачивание завершено. Распаковка...")

            self.finished.emit(True, release_version, zip_path)

        except Exception as e:
            msg = f"Ошибка проверки обновлений: {str(e)}"
            if not self.silent:
                self.finished.emit(False, msg, "")
            else:
                self.finished.emit(False, "", "")


class UpdateManager:
    def __init__(self, parent_window=None):
        self.parent = parent_window
        self.script_dir = self._get_app_dir()
        self.exe_path = sys.executable
        self.app_folder = os.path.dirname(self.exe_path)  # .../DocumentFiller
        self.config = self._load_config()
        self.current_version = self._get_current_version()
        self.repo = self.config.get("github_repo", "").replace("https://github.com/", "").rstrip("/")

        # Автоматическая проверка при запуске (через 8–12 секунд)
        QTimer.singleShot(10000, self._auto_check)

    def _get_app_dir(self):
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        return os.path.dirname(os.path.abspath(__file__))

    def _load_config(self):
        try:
            path = os.path.join(self.script_dir, "repo_config.json")
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}

    def _get_current_version(self):
        try:
            from version import __version__
            return __version__.strip()
        except:
            return self.config.get("current_version", "0.0.0").strip()

    @staticmethod
    def _clean_version(v: str) -> str:
        v = re.sub(r'[^0-9.]', '', v)
        parts = v.split('.')
        while len(parts) < 3:
            parts.append('0')
        return '.'.join(parts[:3])

    def _is_newer(self, new_v: str, curr_v: str) -> bool:
        def to_tuple(v):
            return tuple(map(int, v.split('.')))
        try:
            return to_tuple(new_v) > to_tuple(curr_v)
        except:
            return False

    def _auto_check(self):
        if not self.repo:
            return
        self.check(silent=True)

    def check(self, silent: bool = False):
        """Публичный метод — можно вызывать из меню "Проверить обновления" """
        if not self.repo:
            if not silent:
                QMessageBox.warning(self.parent, "Обновление", "Автообновление не настроено (нет github_repo в конфиге)")
            return

        worker = UpdateWorker(self.repo, self.current_version, silent=silent)
        worker.progress.connect(self._on_progress)
        worker.message.connect(self._on_message)
        worker.finished.connect(self._on_worker_finished)
        worker.start()

    def _on_progress(self, value: int):
        if hasattr(self, 'progress_dialog'):
            self.progress_dialog.setValue(value)

    def _on_message(self, text: str):
        if hasattr(self, 'progress_dialog'):
            self.progress_dialog.setLabelText(text)

    def _on_worker_finished(self, success: bool, version_or_error: str, zip_path: str):
        if hasattr(self, 'progress_dialog'):
            self.progress_dialog.close()
            del self.progress_dialog

        if not success:
            if version_or_error and not "последняя" in version_or_error.lower():
                QMessageBox.warning(self.parent, "Обновление", version_or_error)
            return

        # Есть новая версия + zip скачан
        reply = QMessageBox.question(
            self.parent,
            "Доступно обновление",
            f"Установлена версия: {self.current_version}\nНовая версия: {version_or_error}\n\nУстановить сейчас?\n(приложение перезапустится)",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )

        if reply == QMessageBox.Yes:
            self._apply_update(version_or_error, zip_path)

    def _apply_update(self, new_version: str, zip_path: str):
        """Распаковка → замена файлов → перезапуск через .bat"""
        try:
            temp_extract = os.path.join(tempfile.gettempdir(), f"docfiller_{new_version}")
            shutil.rmtree(temp_extract, ignore_errors=True)
            os.makedirs(temp_extract, exist_ok=True)

            with zipfile.ZipFile(zip_path, 'r') as z:
                z.extractall(temp_extract)

            # Ищем папку DocumentFiller внутри распакованного
            new_app_root = None
            for root, dirs, _ in os.walk(temp_extract):
                if "DocumentFiller.exe" in os.listdir(root):
                    new_app_root = root
                    break

            if not new_app_root:
                QMessageBox.critical(self.parent, "Ошибка", "Не найдена структура DocumentFiller в архиве")
                return

            new_exe = os.path.join(new_app_root, "DocumentFiller.exe")

            # Создаём bat для замены
            bat_path = os.path.join(tempfile.gettempdir(), "update_docfiller.bat")
            bat_content = f"""@echo off
timeout /t 3 >nul

echo Replacing application files...

:: Копируем всё новое поверх старого
xcopy "{new_app_root}\\*.*" "{self.app_folder}" /E /H /C /I /Y /Q

:: Запускаем обновлённую программу
start "" "{self.exe_path}"

:: Удаляем временные файлы
timeout /t 4 >nul
rmdir /s /q "{temp_extract}"
del "{zip_path}"
del "%~f0"
"""

            with open(bat_path, "w", encoding="cp1251") as f:
                f.write(bat_content)

            # Запускаем bat и выходим
            subprocess.Popen(
                ["cmd.exe", "/c", "start", "/min", bat_path],
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
            )

            QMessageBox.information(
                self.parent, "Обновление",
                "Обновление подготовлено.\nПрограмма сейчас перезапустится с новой версией."
            )
            sys.exit(0)

        except Exception as e:
            QMessageBox.critical(self.parent, "Ошибка обновления", str(e))

    # Для меню — пример создания действия
    def create_menu_action(self, menu):
        action = QAction("Проверить обновления", self.parent)
        action.triggered.connect(lambda: self.check(silent=False))
        menu.addAction(action)
        return action


# Пример интеграции в MainWindow:
"""
self.update_manager = UpdateManager(self)
# в меню Сервис
service_menu.addAction(self.update_manager.create_menu_action(service_menu))
"""