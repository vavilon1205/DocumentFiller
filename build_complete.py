# build_complete.py - полная сборка со всеми зависимостями
import os
import shutil
import subprocess
import sys
from pathlib import Path
import json


def install_pyinstaller():
    """Установить PyInstaller если не установлен"""
    try:
        import PyInstaller
        print("✅ PyInstaller уже установлен")
        return True
    except ImportError:
        print("Установка PyInstaller...")
        try:
            subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyinstaller'], check=True)
            print("✅ PyInstaller успешно установлен")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Ошибка установки PyInstaller: {e}")
            return False


def build_complete():
    print("Полная сборка со всеми зависимостями...")

    # Установка PyInstaller если нужно
    if not install_pyinstaller():
        print("Не удалось установить PyInstaller, создаем портативное решение...")
        create_portable_solution()
        return

    # Создаем недостающие конфиги
    create_missing_configs()

    # Очистка предыдущих сборок
    for folder in ['build', 'dist']:
        if os.path.exists(folder):
            shutil.rmtree(folder)

    # Создаем оптимизированный spec файл для быстрого запуска
    create_optimized_spec_file()

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


def create_optimized_spec_file():
    """Создать оптимизированный spec файл для быстрого запуска"""

    # Проверяем существование папки Шаблоны
    templates_exists = os.path.exists('Шаблоны')

    # Формируем datas правильно
    datas_content = [
        "('version_config.json', '.'),",
        "('repo_config.json', '.'),"
    ]

    if templates_exists:
        datas_content.append("('Шаблоны', 'Шаблоны'),")

    datas_str = '\n        '.join(datas_content)

    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
# optimized_build.spec - оптимизированная сборка для быстрого запуска

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        {datas_str}
    ],
    hiddenimports=[
        # Только самые необходимые модули
        'openpyxl', 'docxtpl', 'jinja2', 'docx',
        'lxml.etree', 'lxml._elementpath',

        # PyQt5 модули
        'PyQt5', 'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets', 'PyQt5.QtNetwork',
        'PyQt5.sip',

        # Наши модули
        'main_window',
        'settings', 
        'theme_manager',
        'license_manager',
        'update_manager',
        'widgets',

        # Модули для работы с сетью
        'requests',
        'urllib3',
        'chardet',
        'idna',
        'certifi',

        # Стандартные модули Python
        'json',
        'zipfile',
        'tempfile',
        'datetime',
        'hashlib',
        'uuid',
        'platform',
        're',
        'threading',
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[
        # Исключаем всё ненужное для ускорения запуска
        'tkinter', 'unittest', 'test', 'pydoc', 'email',
        'numpy', 'pandas', 'scipy', 'matplotlib', 'PIL',
        'pygame', 'wx', 'gtk', 'curses', 'multiprocessing',
        'concurrent', 'html', 'http', 'xmlrpc', 'ssl',
        'asyncio', 'selectors', 'distutils', 'setuptools',
        'pip', 'wheel', 'pkg_resources',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
    optimize=2,
)

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
    upx=True,
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

    with open('complete_build.spec', 'w', encoding='utf-8') as f:
        f.write(spec_content)
    print("Создан оптимизированный complete_build.spec для быстрого запуска")
    if templates_exists:
        print("✅ Папка 'Шаблоны' включена в сборку")


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

        # Оптимизация: удаляем ненужные файлы для ускорения запуска
        optimize_distribution(dist_dir)
    else:
        # Для сборки onefile
        exe_source = 'dist/DocumentFiller.exe'
        if os.path.exists(exe_source):
            os.makedirs(dist_dir)
            shutil.copy2(exe_source, dist_dir)
            print(f"Скопирован EXE файл: {exe_source}")

    # Копируем дополнительные файлы (только если они существуют)
    additional_files = ['version_config.json', 'repo_config.json']
    for file in additional_files:
        if os.path.exists(file):
            shutil.copy2(file, dist_dir)
            print(f"Добавлен {file}")

    # Копируем папку Шаблоны если она существует
    if os.path.exists('Шаблоны'):
        shutil.copytree('Шаблоны', os.path.join(dist_dir, 'Шаблоны'))
        print("✅ Папка 'Шаблоны' скопирована")

    create_readme(dist_dir)
    print(f"\n🎉 ФИНАЛЬНАЯ СБОРКА СОЗДАНА В: {dist_dir}")


def optimize_distribution(dist_dir):
    """Оптимизировать дистрибуцию для быстрого запуска"""
    print("Оптимизация дистрибуции для быстрого запуска...")

    # Удаляем ненужные файлы и папки
    unnecessary_items = [
        'tcl', 'tk', 'sqlite3', 'lib2to3',
        'pydoc_data', 'test', 'unittest',
    ]

    for item in unnecessary_items:
        item_path = os.path.join(dist_dir, item)
        if os.path.exists(item_path):
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
                print(f"Удалена папка: {item}")
            else:
                os.remove(item_path)
                print(f"Удален файл: {item}")


def create_backup_solution():
    """Создать резервное решение"""
    print("Создаем резервное решение...")

    try:
        # Простая сборка с основными параметрами
        params = [
            'main.py',
            '--name=DocumentFiller',
            '--windowed',
            '--onedir',
            '--clean',
            '--noconfirm',
            '--add-data=version_config.json;.',
            '--add-data=repo_config.json;.',
        ]

        # Добавляем папку Шаблоны если она существует
        if os.path.exists('Шаблоны'):
            params.append('--add-data=Шаблоны;Шаблоны')

        # Запускаем PyInstaller
        subprocess.run([sys.executable, '-m', 'PyInstaller'] + params, check=True)
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
        'update_manager.py', 'license_manager.py', 'widgets.py',
        'version_config.json', 'repo_config.json'
    ]

    for file in python_files:
        if os.path.exists(file):
            shutil.copy2(file, portable_dir)
            print(f"Скопирован {file}")

    # Копируем папку Шаблоны если она существует
    if os.path.exists('Шаблоны'):
        shutil.copytree('Шаблоны', os.path.join(portable_dir, 'Шаблоны'))
        print("✅ Папка 'Шаблоны' скопирована")

    create_readme(portable_dir)
    print(f"\n📦 ПОРТАТИВНОЕ РЕШЕНИЕ СОЗДАНО: {portable_dir}")


def create_readme(dist_dir):
    """Создать README файл"""
    readme_content = '''DocumentFiller - Программа для заполнения документов

ЗАПУСК:
1. Для версии с EXE - запустите DocumentFiller.exe
2. Для портативной версии:
   - Запустите install_dependencies.bat (если зависимости не установлены)
   - Запустите start.bat

СТРУКТУРА ПАПОК:
- Шаблоны/ - папка с шаблонами документов (.docx)
- документы/ - папка для сохранения заполненных документов (создается автоматически)

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