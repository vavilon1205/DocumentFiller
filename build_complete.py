# build_complete.py - исправленная версия
import os
import shutil
import subprocess
import sys
import json
from pathlib import Path
import zipfile  # Добавляем импорт


def build_complete():
    print("🚀 Запуск сборки...")

    # Загружаем версию из repo_config.json
    version = load_version_from_config()
    if not version:
        print("❌ Не удалось загрузить версию из repo_config.json")
        return False

    print(f"📋 Версия для сборки: {version}")

    # Проверяем существование папки с шаблонами
    templates_dir = "Шаблоны"
    if not os.path.exists(templates_dir):
        print(f"❌ Папка '{templates_dir}' не найдена!")
        print("Создайте папку 'Шаблоны' с шаблонами документов перед сборкой.")
        return False

    # Создаем правильный spec файл
    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-

import sys
from PyInstaller.building.build_main import Analysis
from PyInstaller.building.api import PYZ, EXE, COLLECT

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('repo_config.json', '.'),
        ('Шаблоны', 'Шаблоны')
    ],
    hiddenimports=[
        'main_window', 'settings', 'theme_manager', 
        'license_manager', 'update_manager', 'widgets',
        'PyQt5', 'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets', 'PyQt5.QtNetwork',
        'PyQt5.sip',
        'openpyxl', 'docxtpl', 'jinja2', 'docx',
        'lxml', 'lxml.etree', 'lxml._elementpath',
        'requests', 'urllib3', 'chardet', 'idna', 'certifi',
        'email', 'email.mime', 'email.mime.text', 'email.mime.multipart',
        'email.mime.base', 'email.encoders', 'email.utils',
        'hashlib', 'json', 'datetime', 'os', 'sys', 're',
        'uuid', 'platform', 'threading', 'tempfile', 'zipfile',
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='DocumentFiller',  # Фиксированное имя для обновлений
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
'''

    spec_filename = 'document_filler.spec'
    with open(spec_filename, 'w', encoding='utf-8') as f:
        f.write(spec_content)

    # Очищаем папки перед сборкой
    for dir_name in ['dist', 'build']:
        if os.path.exists(dir_name):
            print(f"🧹 Очистка папки {dir_name}...")
            shutil.rmtree(dir_name)

    # Запускаем сборку
    try:
        print("🔨 Запуск PyInstaller...")
        result = subprocess.run([
            sys.executable, '-m', 'PyInstaller',
            spec_filename, '--noconfirm', '--clean'
        ], check=True, capture_output=True, text=True)

        print("✅ Сборка завершена успешно!")

        # Переименовываем EXE файл чтобы включить версию
        original_exe = os.path.join('dist', 'DocumentFiller.exe')
        versioned_exe = os.path.join('dist', f'DocumentFiller_v{version}.exe')

        if os.path.exists(original_exe):
            shutil.copy2(original_exe, versioned_exe)
            print(f"📦 Создан EXE с версией: {versioned_exe}")

        # Проверяем наличие шаблонов
        templates_in_dist = os.path.join('dist', 'DocumentFiller', 'Шаблоны')
        if os.path.exists(templates_in_dist):
            print("✅ Шаблоны скопированы в папку dist")

            # Показываем размер
            total_size = 0
            for root, dirs, files in os.walk('dist'):
                for file in files:
                    file_path = os.path.join(root, file)
                    total_size += os.path.getsize(file_path)

            print(f"📊 Общий размер: {total_size / (1024 * 1024):.2f} МБ")
            return True
        else:
            print("❌ Шаблоны не скопированы в папку dist!")
            return False

    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка сборки: {e}")
        if e.stderr:
            print(f"Детали: {e.stderr}")
        return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return False
    finally:
        # Очищаем временные файлы
        clean_temp_files()

def load_version_from_config():
    """Загрузить версию из repo_config.json"""
    try:
        if os.path.exists("repo_config.json"):
            with open("repo_config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
                version = config.get("current_version", "1.0.0")
                # Убедимся, что версия в правильном формате (без пробелов, специальных символов)
                version = version.replace(' ', '_').replace('/', '_').replace('\\', '_')
                return version
        else:
            # Создаем конфиг по умолчанию
            default_config = {
                "type": "yandex_disk",
                "yandex_disk_url": "",
                "current_version": "1.0.0",
                "online_license_db_url": ""
            }
            with open("repo_config.json", "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            return "1.0.0"
    except Exception as e:
        print(f"❌ Ошибка загрузки версии: {e}")
        return "1.0.0"


def clean_temp_files():
    """Очистка временных файлов"""
    try:
        # Удаляем все spec файлы
        for file in os.listdir('.'):
            if file.startswith('document_filler_v') and file.endswith('.spec'):
                os.remove(file)
                print(f"🧹 Удален временный файл: {file}")

        # Удаляем временную папку сборки
        build_temp_dir = 'build_temp'
        if os.path.exists(build_temp_dir):
            shutil.rmtree(build_temp_dir)
            print("🧹 Временная папка сборки очищена")
    except Exception as e:
        print(f"⚠️ Не удалось очистить временные файлы: {e}")


def create_release_zip():
    """Создать ZIP архив с готовым приложением"""
    try:
        version = load_version_from_config()
        dist_dir = 'dist'

        if not os.path.exists(dist_dir):
            print("❌ Папка dist не найдена!")
            return False

        exe_name = f'DocumentFiller_v{version}.exe'
        exe_path = os.path.join(dist_dir, exe_name)

        if not os.path.exists(exe_path):
            print(f"❌ EXE файл {exe_name} не найден!")
            return False

        # Создаем ZIP архив
        zip_filename = f'DocumentFiller_v{version}.zip'
        print(f"🗜️ Создание ZIP архива: {zip_filename}")

        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Добавляем EXE файл
            zipf.write(exe_path, exe_name)

            # Добавляем папку Шаблоны
            templates_dir = os.path.join(dist_dir, 'Шаблоны')
            if os.path.exists(templates_dir):
                for root, dirs, files in os.walk(templates_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.join('Шаблоны', os.path.relpath(file_path, templates_dir))
                        zipf.write(file_path, arcname)

            # Добавляем repo_config.json
            if os.path.exists('repo_config.json'):
                zipf.write('repo_config.json', 'repo_config.json')

        print(f"✅ ZIP архив создан: {zip_filename}")
        return True

    except Exception as e:
        print(f"❌ Ошибка создания ZIP архива: {e}")
        return False


if __name__ == "__main__":
    # Проверяем необходимые файлы перед сборкой
    required_files = ['main.py', 'main_window.py']
    missing_files = []

    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)

    if missing_files:
        print("❌ Отсутствуют необходимые файлы для сборки:")
        for file in missing_files:
            print(f"   - {file}")
        print("Убедитесь, что все файлы находятся в текущей папке.")
        sys.exit(1)

    # Проверяем наличие папки Шаблоны
    if not os.path.exists("Шаблоны"):
        print("❌ Папка 'Шаблоны' не найдена!")
        print("Создайте папку 'Шаблоны' и добавьте туда шаблоны документов (.docx)")
        sys.exit(1)

    # Проверяем наличие repo_config.json
    if not os.path.exists("repo_config.json"):
        print("⚠️  Файл repo_config.json не найден, создаем с настройками по умолчанию...")
        load_version_from_config()  # Это создаст файл

    # Запускаем сборку
    success = build_complete()

    if success:
        print("\n🎉 Сборка успешно завершена!")
        version = load_version_from_config()
        print(f"📦 Имя EXE файла: DocumentFiller_v{version}.exe")
        print("📍 Готовое приложение находится в папке 'dist'")

        # Предлагаем создать ZIP архив
        create_zip = input("\n🗜️  Создать ZIP архив для распространения? (y/n): ").lower().strip()
        if create_zip in ['y', 'yes', 'д', 'да']:
            if create_release_zip():
                print("✅ ZIP архив создан и готов для распространения!")
            else:
                print("❌ Не удалось создать ZIP архив")
    else:
        print("\n💥 Сборка не удалась!")
        sys.exit(1)