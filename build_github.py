# build_github.py - скрипт сборки для GitHub репозитория
import os
import shutil
import subprocess
import sys
import json
from datetime import datetime
import zipfile


def build_github():
    print("🚀 Запуск сборки для GitHub репозитория...")

    # Запрашиваем версию у пользователя
    version = input("Введите версию для сборки (например 1.0.1): ").strip()
    if not version:
        print("❌ Версия не указана")
        return False

    # Фиксированные настройки для GitHub репозитория
    github_repo = "https://github.com/vavilon1205/DocumentFiller"
    update_url = "https://github.com/vavilon1205/DocumentFiller/releases/latest"

    print(f"📋 Сборка версии: {version}")
    print(f"📦 GitHub репозиторий: {github_repo}")

    # Обновляем версию в version.py
    try:
        version_content = f'# version.py - хранение версии в коде\n__version__ = "{version}"\n'
        with open("version.py", "w", encoding="utf-8") as f:
            f.write(version_content)
        print(f"✅ Версия обновлена в version.py: {version}")
    except Exception as e:
        print(f"❌ Ошибка обновления version.py: {e}")
        return False

    # Создаем repo_config.json с актуальной информацией
    try:
        config = {
            "type": "github",
            "github_repo": github_repo,
            "current_version": version,
            "update_url": update_url,
            "online_license_db_url": ""
        }

        with open("repo_config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print(f"✅ Конфиг обновлен: версия={version}, репозиторий={github_repo}")
    except Exception as e:
        print(f"❌ Ошибка обновления repo_config.json: {e}")
        return False

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

    spec_filename = 'document_filler_github.spec'
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

        # Создаем файлы для GitHub Releases
        original_exe_dir = os.path.join('dist', 'DocumentFiller')
        original_exe = os.path.join(original_exe_dir, 'DocumentFiller.exe')

        if os.path.exists(original_exe):
            # Создаем EXE файл с версией в названии
            versioned_exe_name = f'DocumentFiller_v{version}.exe'
            versioned_exe = os.path.join('dist', versioned_exe_name)
            shutil.copy2(original_exe, versioned_exe)
            print(f"📦 Создан EXE для GitHub: {versioned_exe_name}")

            # Создаем ZIP архив с версией
            zip_filename = f'DocumentFiller_v{version}.zip'
            create_github_zip(original_exe_dir, zip_filename)
            print(f"📦 Создан ZIP архив: {zip_filename}")

            # Создаем инструкцию
            create_github_instructions(version, versioned_exe_name, zip_filename)

        # Проверяем результат
        if os.path.exists(original_exe_dir):
            print(f"📁 Содержимое папки dist:")
            for item in os.listdir('dist'):
                item_path = os.path.join('dist', item)
                if os.path.isfile(item_path):
                    size = os.path.getsize(item_path) / (1024 * 1024)
                    print(f"   📄 {item} ({size:.2f} МБ)")

            print(f"\n🎉 Сборка для GitHub завершена!")
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


def create_github_zip(source_dir, zip_filename):
    """Создать ZIP архив для GitHub"""
    try:
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(source_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, os.path.dirname(source_dir))
                    zipf.write(file_path, arcname)

        # Перемещаем ZIP в dist
        dist_zip = os.path.join('dist', zip_filename)
        if os.path.exists(zip_filename):
            shutil.move(zip_filename, dist_zip)

        return True
    except Exception as e:
        print(f"❌ Ошибка создания ZIP: {e}")
        return False


def create_github_instructions(version, exe_name, zip_name):
    """Создать инструкцию по загрузке в GitHub Releases"""
    instructions = f"""
📋 ИНСТРУКЦИЯ ПО ЗАГРУЗКЕ В GITHUB RELEASES:

1. Перейдите на страницу репозитория: https://github.com/vavilon1205/DocumentFiller
2. Нажмите "Create a new release" или выберите существующий релиз
3. Для нового релиза:
   - Tag: v{version}
   - Title: DocumentFiller v{version}
   - Description: Опишите изменения в этой версии

4. Загрузите файлы из папки 'dist':
   - {exe_name} (отдельный EXE)
   - {zip_name} (ZIP архив)

5. Опубликуйте релиз

6. После публикации программа сможет автоматически находить обновления!

🔗 Ссылка для скачивания будет: 
https://github.com/vavilon1205/DocumentFiller/releases/latest/download/{exe_name}

⚙️ Конфигурация обновлений:
- Репозиторий: https://github.com/vavilon1205/DocumentFiller
- Текущая версия: {version}
- Автоматические проверки: Включены
"""

    instructions_file = "github_release_instructions.txt"
    with open(instructions_file, "w", encoding="utf-8") as f:
        f.write(instructions)

    print(f"📄 Создана инструкция: {instructions_file}")
    print(instructions)


def clean_temp_files():
    """Очистка временных файлов"""
    try:
        if os.path.exists('document_filler_github.spec'):
            os.remove('document_filler_github.spec')
            print("🧹 Удален временный файл: document_filler_github.spec")

        build_dir = 'build'
        if os.path.exists(build_dir):
            shutil.rmtree(build_dir)
            print("🧹 Временная папка сборки очищена")
    except Exception as e:
        print(f"⚠️ Не удалось очистить временные файлы: {e}")


if __name__ == "__main__":
    # Проверяем необходимые файлы
    required_files = ['main.py', 'main_window.py', 'version.py', 'update_manager.py']
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
    success = build_github()

    if success:
        print("\n✅ Сборка для GitHub успешно завершена!")
        print("📍 Готовые файлы находятся в папке 'dist'")
        print("\n📤 Загрузите файлы в GitHub Releases согласно инструкции")
        print("\n🔔 Программа теперь будет автоматически проверять обновления из GitHub!")
    else:
        print("\n💥 Сборка не удалась!")
        sys.exit(1)