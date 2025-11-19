# build_complete.py - полная сборка со всеми зависимостями
import os
import shutil
import subprocess
import sys
from pathlib import Path


def build_complete():
    print("Полная сборка со всеми зависимостями...")

    # Создаем недостающие конфиги
    create_missing_configs()

    # Очистка предыдущих сборок
    for folder in ['build', 'dist']:
        if os.path.exists(folder):
            shutil.rmtree(folder)

    # Создаем полный spec файл
    create_complete_spec_file()

    # Запускаем сборку
    try:
        subprocess.run([sys.executable, '-m', 'PyInstaller', 'complete_build.spec', '--clean'], check=True)
        print("✅ Полная сборка завершена успешно!")
        create_final_distribution()
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка сборки: {e}")
        create_backup_solution()


def create_missing_configs():
    """Создать недостающие конфигурационные файлы"""
    import json

    configs = {
        'repo_config.json': {
            "type": "github",
            "owner": "your-username",
            "repo": "your-repo-name",
            "branch": "main",
            "token": ""
        },
        'version_config.json': {
            "current_version": "1.0.0",
            "update_url": "",
            "check_updates_on_start": False,
            "update_channel": "stable"
        }
    }

    for filename, config in configs.items():
        if not os.path.exists(filename):
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            print(f"Создан {filename}")


def create_complete_spec_file():
    """Создать полный spec файл со всеми зависимостями"""
    spec_content = '''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('version_config.json', '.'),
        ('repo_config.json', '.'),
        ('*.docx', '.'),
        ('*.xlsx', '.'),
    ],
    hiddenimports=[
        # Основные модули
        'openpyxl', 'docxtpl', 'jinja2', 'docx',
        'lxml', 'lxml.etree', 'lxml._elementpath',

        # PyQt5 модули
        'PyQt5', 'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets', 'PyQt5.QtNetwork',
        'PyQt5.sip',

        # Модули для работы с сетью
        'requests',
        'urllib3',
        'chardet',
        'idna',
        'certifi',

        # Дополнительные модули
        'json',
        'zipfile',
        'tempfile',
        'datetime',
        'hashlib',
        'uuid',
        'platform',
        're',
        'threading',
        'sys',
        'os',
        'shutil',
        'subprocess',
        'pathlib',

        # Модули для работы с документами
        'docx2txt',
        'docxcompose',
        'docxtpl',
        'jinja2',
        'jinja2.ext',

        # Модули Excel
        'openpyxl',
        'openpyxl.workbook',
        'openpyxl.worksheet',
        'openpyxl.cell',
        'openpyxl.styles',

        # Модули лицензирования
        'hashlib',
        'secrets',
        'base64',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'unittest', 'test', 'pydoc', 'email',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Собираем все ресурсы критически важных пакетов
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='DocumentFiller',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=get_icon_path(),
)

# Добавляем бинарные файлы и данные отдельно
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='DocumentFiller',
)
'''

    with open('complete_build.spec', 'w', encoding='utf-8') as f:
        f.write(spec_content)
    print("Создан complete_build.spec")


def get_icon_path():
    """Получить путь к иконке для spec файла"""
    icon_paths = ['icon.ico', 'icon.png', 'assets/icon.ico']
    for path in icon_paths:
        if os.path.exists(path):
            return path
    return None


def create_final_distribution():
    """Создать финальную дистрибуцию"""
    dist_dir = 'DocumentFiller_Final'
    if os.path.exists(dist_dir):
        shutil.rmtree(dist_dir)

    # Для сборки в одну папку
    source_dir = 'dist/DocumentFiller'
    if os.path.exists(source_dir):
        shutil.copytree(source_dir, dist_dir)
        print(f"Скопирована папка сборки: {source_dir} -> {dist_dir}")
    else:
        # Для сборки onefile
        exe_source = 'dist/DocumentFiller.exe'
        if os.path.exists(exe_source):
            os.makedirs(dist_dir)
            shutil.copy2(exe_source, dist_dir)
            print(f"Скопирован EXE файл: {exe_source}")

    # Копируем дополнительные файлы
    additional_files = ['version_config.json', 'repo_config.json', '*.docx', '*.xlsx']
    for pattern in additional_files:
        for file_path in Path('.').glob(pattern):
            if file_path.name not in ['build_complete.py']:
                shutil.copy2(file_path, dist_dir)
                print(f"Добавлен {file_path}")

    create_readme(dist_dir)
    print(f"\\n🎉 ФИНАЛЬНАЯ СБОРКА СОЗДАНА В: {dist_dir}")


def create_backup_solution():
    """Создать резервное решение"""
    print("Создаем резервное решение...")

    # Пробуем простую сборку с явным указанием всех модулей
    try:
        import PyInstaller.__main__

        params = [
            'main.py',
            '--name=DocumentFiller',
            '--windowed',
            '--onedir',  # Используем onedir для надежности
            '--clean',
            '--noconfirm',
            '--noupx',
            '--add-data=version_config.json;.',
            '--add-data=repo_config.json;.',
            '--add-data=*.docx;.',
            '--add-data=*.xlsx;.',
            # Все скрытые импорты
            '--hidden-import=requests',
            '--hidden-import=urllib3',
            '--hidden-import=chardet',
            '--hidden-import=idna',
            '--hidden-import=certifi',
            '--hidden-import=PyQt5',
            '--hidden-import=PyQt5.QtCore',
            '--hidden-import=PyQt5.QtGui',
            '--hidden-import=PyQt5.QtWidgets',
            '--hidden-import=PyQt5.QtNetwork',
            '--hidden-import=openpyxl',
            '--hidden-import=docxtpl',
            '--hidden-import=jinja2',
            '--hidden-import=docx',
            '--hidden-import=lxml',
            '--hidden-import=lxml.etree',
            # Собираем все ресурсы
            '--collect-all=requests',
            '--collect-all=PyQt5',
            '--collect-all=openpyxl',
        ]

        PyInstaller.__main__.run(params)
        print("✅ Резервная сборка завершена!")
        create_final_distribution()

    except Exception as e:
        print(f"❌ Резервная сборка не удалась: {e}")
        create_portable_solution()


def create_portable_solution():
    """Создать портативное решение"""
    print("Создаем портативное решение...")

    portable_dir = 'DocumentFiller_Portable'
    if os.path.exists(portable_dir):
        shutil.rmtree(portable_dir)

    os.makedirs(portable_dir)

    # Создаем файл требований
    requirements_content = '''PyQt5>=5.15
openpyxl>=3.0
python-docx>=0.8
docxtpl>=0.16
jinja2>=3.0
lxml>=4.6
requests>=2.25
'''

    with open(os.path.join(portable_dir, 'requirements.txt'), 'w', encoding='utf-8') as f:
        f.write(requirements_content)

    # Создаем установщик зависимостей
    install_bat = '''@echo off
chcp 65001
title Установка зависимостей DocumentFiller
echo Установка необходимых библиотек...
echo.

python -m pip install --upgrade pip
pip install -r requirements.txt

echo.
echo Установка завершена!
echo Запустите start.bat для запуска программы
pause
'''

    with open(os.path.join(portable_dir, 'install_dependencies.bat'), 'w', encoding='utf-8') as f:
        f.write(install_bat)

    # Создаем запускатор
    start_bat = '''@echo off
chcp 65001
title DocumentFiller
echo Запуск программы...
python main.py
pause
'''

    with open(os.path.join(portable_dir, 'start.bat'), 'w', encoding='utf-8') as f:
        f.write(start_bat)

    # Копируем все исходные файлы Python
    python_files = [
        'main.py', 'main_window.py', 'settings.py', 'theme_manager.py',
        'updater.py', 'license_manager.py', 'widgets.py',
        'version_config.json', 'repo_config.json'
    ]

    for file in python_files:
        if os.path.exists(file):
            shutil.copy2(file, portable_dir)
            print(f"Скопирован {file}")

    # Копируем шаблоны документов и данные
    for pattern in ['*.docx', '*.xlsx']:
        for file_path in Path('.').glob(pattern):
            shutil.copy2(file_path, portable_dir)
            print(f"Скопирован {file_path}")

    create_readme(portable_dir)
    print(f"\\n📦 ПОРТАТИВНОЕ РЕШЕНИЕ СОЗДАНО: {portable_dir}")


def create_readme(dist_dir):
    """Создать README файл"""
    readme_content = '''DocumentFiller - Программа для заполнения документов

ЗАПУСК:
1. Для версии с EXE - запустите DocumentFiller.exe
2. Для портативной версии:
   - Запустите install_dependencies.bat (если зависимости не установлены)
   - Запустите start.bat

ТРЕБОВАНИЯ:
- Windows 7/8/10/11
- Python 3.8+ (для портативной версии)
- Установленные библиотеки (устанавливаются автоматически)

ПОДДЕРЖКА:
Разработчик: Строчков Сергей Константинович
Телефон: 8(920)791-30-43
'''

    with open(os.path.join(dist_dir, 'README.txt'), 'w', encoding='utf-8') as f:
        f.write(readme_content)


if __name__ == "__main__":
    build_complete()