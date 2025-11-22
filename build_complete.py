# build_complete.py - УЛУЧШЕННАЯ СБОРКА
import os
import shutil
import subprocess
import sys
from pathlib import Path


def build_complete():
    print("🚀 Запуск улучшенной сборки...")

    # Создаем правильный spec файл
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
        ('version_config.json', '.'),
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

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DocumentFiller'
)
'''

    with open('document_filler.spec', 'w', encoding='utf-8') as f:
        f.write(spec_content)

    # Запускаем сборку
    try:
        result = subprocess.run([
            sys.executable, '-m', 'PyInstaller',
            'document_filler.spec', '--clean', '--noconfirm'
        ], check=True, capture_output=True, text=True)

        print("✅ Сборка завершена успешно!")

        # Проверяем результат
        dist_dir = 'dist/DocumentFiller'
        if os.path.exists(dist_dir):
            exe_path = os.path.join(dist_dir, 'DocumentFiller.exe')
            if os.path.exists(exe_path):
                print(f"📦 EXE создан: {exe_path}")

                # Проверяем DLL
                dll_files = [f for f in os.listdir(dist_dir) if f.endswith('.dll')]
                print(f"📁 Найдено DLL файлов: {len(dll_files)}")
                for dll in dll_files:
                    print(f"   - {dll}")

                # Создаем релизный пакет
                from create_release import create_release_package
                create_release_package()

                return True

        print("❌ Сборка не удалась")
        return False

    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка сборки: {e}")
        if e.stderr:
            print(f"Детали: {e.stderr}")
        return False


if __name__ == "__main__":
    build_complete()