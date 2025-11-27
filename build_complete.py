# build_complete.py - ИСПРАВЛЕННАЯ ВЕРСИЯ ДЛЯ MAIL.RU CLOUD
import os
import shutil
import subprocess
import sys
import json
from pathlib import Path
import zipfile


def build_complete():
    print("🚀 Запуск сборки...")

    # Запрашиваем версию у пользователя
    version = input("Введите версию для сборки (например 1.0.1): ").strip()
    if not version:
        print("❌ Версия не указана")
        return False

    # Запрашиваем URL папки на Облаке Mail.ru
    print("\n📝 Настройка обновлений:")
    print("Укажите публичную ссылку на папку в Облаке Mail.ru")
    print("Пример: https://cloud.mail.ru/public/49wa/SD8CijQJ5")
    mail_ru_cloud_url = input("URL папки в Облаке Mail.ru: ").strip()

    if not mail_ru_cloud_url:
        print("⚠️ URL папки не указан - автообновления отключены")

    # Обновляем версию в version.py
    try:
        version_content = f'# version.py - хранение версии в коде\n__version__ = "{version}"\n'
        with open("version.py", "w", encoding="utf-8") as f:
            f.write(version_content)
        print(f"✅ Версия обновлена в version.py: {version}")
    except Exception as e:
        print(f"❌ Ошибка обновления version.py: {e}")
        return False

    # Обновляем repo_config.json
    try:
        config = {
            "type": "mail_ru_cloud",
            "mail_ru_cloud_url": mail_ru_cloud_url,
            "current_version": version,
            "online_license_db_url": ""
        }

        with open("repo_config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print(f"✅ Конфиг обновлен: версия={version}, папка={mail_ru_cloud_url}")
    except Exception as e:
        print(f"❌ Ошибка обновления repo_config.json: {e}")
        return False

    print(f"📋 Сборка версии: {version}")
    if mail_ru_cloud_url:
        print(f"📁 Папка для обновлений: {mail_ru_cloud_url}")

    # Проверяем существование папки с шаблонами
    templates_dir = "Шаблоны"
    if not os.path.exists(templates_dir):
        print(f"❌ Папка '{templates_dir}' не найдена!")
        print("Создайте папку 'Шаблоны' с шаблонами документов перед сборкой.")
        return False

    # Создаем spec файл
    spec_content = '''# -*- mode: python ; coding: utf-8 -*-

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
        ('Шаблоны', 'Шаблоны'),
        ('version.py', '.')
    ],
    hiddenimports=[
        'main_window', 'settings', 'theme_manager', 
        'license_manager', 'update_manager', 'widgets', 'version',
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
    hooksconfig={},
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
    name='DocumentFiller',
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

        # Создаем понятные файлы для загрузки в Облако Mail.ru
        original_exe_dir = os.path.join('dist', 'DocumentFiller')
        original_exe = os.path.join(original_exe_dir, 'DocumentFiller.exe')

        if os.path.exists(original_exe):
            # Создаем файл с версией в названии для загрузки
            versioned_exe_name = f'DocumentFiller_v{version}.exe'
            versioned_exe = os.path.join(original_exe_dir, versioned_exe_name)
            shutil.copy2(original_exe, versioned_exe)
            print(f"📦 Создан EXE для загрузки: {versioned_exe_name}")

            # Также создаем ZIP архив для загрузки
            zip_filename = f'DocumentFiller_v{version}.zip'
            self_extracting_zip = create_self_extracting_zip(original_exe_dir, zip_filename, version)
            print(f"📦 Создан самораспаковывающийся архив: {self_extracting_zip}")

        # Проверяем результат
        if os.path.exists(original_exe_dir):
            print(f"📁 Содержимое папки dist/DocumentFiller:")
            for item in os.listdir(original_exe_dir):
                item_path = os.path.join(original_exe_dir, item)
                if os.path.isfile(item_path):
                    size = os.path.getsize(item_path) / (1024 * 1024)
                    print(f"   📄 {item} ({size:.2f} МБ)")
                else:
                    item_count = len(os.listdir(item_path))
                    print(f"   📂 {item}/ ({item_count} файлов)")

            # Инструкция по загрузке в Облако Mail.ru
            if mail_ru_cloud_url:
                print(f"\n📋 ИНСТРУКЦИЯ ПО ЗАГРУЗКЕ В ОБЛАКО MAIL.RU:")
                print(f"1. Откройте браузер и перейдите по ссылке: {mail_ru_cloud_url}")
                print(f"2. Нажмите 'Загрузить' и выберите файлы:")
                print(f"   - {versioned_exe_name}")
                print(f"   - {zip_filename}")
                print(f"3. Убедитесь, что файлы загрузились и видны в списке")
                print(f"4. Теперь программа сможет автоматически находить обновления!")

            return True
        else:
            print("❌ Папка с EXE не создана!")
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


def create_self_extracting_zip(source_dir, zip_filename, version):
    """Создать самораспаковывающийся ZIP архив"""
    try:
        # Создаем обычный ZIP архив
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(source_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, source_dir)
                    zipf.write(file_path, arcname)

        print(f"✅ Создан ZIP архив: {zip_filename}")
        return zip_filename

    except Exception as e:
        print(f"❌ Ошибка создания ZIP архива: {e}")
        return None


def clean_temp_files():
    """Очистка временных файлов"""
    try:
        if os.path.exists('document_filler.spec'):
            os.remove('document_filler.spec')
            print("🧹 Удален временный файл: document_filler.spec")

        build_dir = 'build'
        if os.path.exists(build_dir):
            shutil.rmtree(build_dir)
            print("🧹 Временная папка сборки очищена")
    except Exception as e:
        print(f"⚠️ Не удалось очистить временные файлы: {e}")


if __name__ == "__main__":
    # Проверяем необходимые файлы
    required_files = ['main.py', 'main_window.py', 'version.py']
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

    # Запускаем сборку
    success = build_complete()

    if success:
        print("\n🎉 Сборка успешно завершена!")
        print("📍 Готовое приложение находится в папке 'dist/DocumentFiller'")

        print("\n🔔 ВАЖНЫЕ ШАГИ ПОСЛЕ СБОРКИ:")
        print("1. Загрузите созданные EXE и ZIP файлы в папку Облака Mail.ru")
        print("2. Убедитесь, что папка публичная (доступ по ссылке)")
        print("3. Запустите программу и проверьте обновления через меню 'Сервис' -> 'Проверить обновления'")
        print("4. Убедитесь, что программа видит новую версию")
    else:
        print("\n💥 Сборка не удалась!")
        sys.exit(1)