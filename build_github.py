# build_github.py - ПОЛНАЯ СБОРКА ДЛЯ GITHUB В РЕЖИМЕ ONEDIR (2026 — рекомендуется)
import os
import sys
import shutil
import subprocess
import json
from datetime import datetime


def update_version_files(version):
    """Обновить version.py и repo_config.json для GitHub"""
    # version.py
    try:
        with open("version.py", "w", encoding="utf-8") as f:
            f.write(f'# version.py - хранение версии в коде\n__version__ = "{version}"\n')
        print(f"✅ version.py обновлён: v{version}")
    except Exception as e:
        print(f"❌ Ошибка записи version.py: {e}")
        return False

    # repo_config.json — GitHub-релиз
    try:
        config = {
            "type": "github",
            "github_repo": "https://github.com/vavilon1205/DocumentFiller",
            "current_version": version,
            "update_url": "https://github.com/vavilon1205/DocumentFiller/releases/latest",
            "online_license_db_url": ""
        }
        with open("repo_config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print("✅ repo_config.json обновлён (GitHub-релиз)")
        return True
    except Exception as e:
        print(f"❌ Ошибка записи repo_config.json: {e}")
        return False


def build_onedir():
    """Сборка в режиме ONEDIR — самая быстрая по запуску"""
    print("🔨 Сборка приложения в режиме ONEDIR (папка dist/DocumentFiller)...")

    spec_content = '''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('repo_config.json', '.'),
        ('version.py', '.'),
        ('Шаблоны', 'Шаблоны'),
    ],
    hiddenimports=[
        'main_window',
        'settings',
        'theme_manager',
        'license_manager',
        'update_manager',
        'widgets',
        'version',
        'PyQt5',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'PyQt5.QtNetwork',
        'PyQt5.sip',
        'openpyxl',
        'docxtpl',
        'jinja2',
        'docx',
        'lxml.etree',
        'requests',
        'urllib3',
        'certifi',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'numpy',
        'scipy',
        'pandas',
        'matplotlib',
        'PIL',
        'pygame',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
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
    upx=True,                    # можно убрать, если UPX замедляет запуск
    console=False,               # без консоли → красивее для пользователей
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
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

    spec_path = "document_filler_github_onedir.spec"

    try:
        with open(spec_path, "w", encoding="utf-8") as f:
            f.write(spec_content)
        print(f"   → Создан spec: {spec_path}")
    except Exception as e:
        print(f"❌ Не удалось создать .spec файл: {e}")
        return False

    # Запуск PyInstaller
    print("\nЗапускаем PyInstaller (обычно 1–5 минут)...")
    try:
        cmd = [
            sys.executable,
            "-m", "PyInstaller",
            spec_path,
            "--noconfirm",
            "--clean",
            "--log-level", "WARN"
        ]
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("PyInstaller завершил работу успешно.")
        if result.stdout:
            last_lines = result.stdout.splitlines()[-8:]
            print("\n".join(last_lines))
    except subprocess.CalledProcessError as e:
        print("❌ PyInstaller завершился с ошибкой:")
        print(e.stderr[-1200:] if e.stderr else "Нет подробного вывода")
        return False
    except Exception as e:
        print(f"❌ Ошибка при запуске PyInstaller: {e}")
        return False

    # Проверка результата
    final_folder = os.path.join("dist", "DocumentFiller")
    if os.path.exists(final_folder) and os.path.isdir(final_folder):
        exe_path = os.path.join(final_folder, "DocumentFiller.exe")
        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print(f"\n🎉 Готово! Исполняемый файл: {exe_path}")
            print(f"   Размер: ≈ {size_mb:.1f} МБ")
            print("   Папка для распространения: dist/DocumentFiller")
            return True

    print(f"❌ Папка {final_folder} или exe-файл не созданы")
    return False


def clean_temp_files():
    """Очистка временных файлов после сборки"""
    for path in ["document_filler_github_onedir.spec", "build"]:
        try:
            if os.path.isfile(path):
                os.remove(path)
            elif os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
        except:
            pass


def main():
    print("=" * 70)
    print("   СБОРКА DocumentFiller ДЛЯ GITHUB — РЕЖИМ ONEDIR (быстрый запуск)")
    print("   Рекомендуется в 2026 году вместо onefile + bootstrap")
    print("=" * 70)

    # Проверка обязательных файлов
    required = ["main.py", "main_window.py", "bootstrap.py", "version.py",
                "update_manager.py", "license_manager.py", "widgets.py", "Шаблоны"]
    missing = [f for f in required if not os.path.exists(f)]
    if missing:
        print("❌ Отсутствуют файлы:")
        for f in missing:
            print(f"   • {f}")
        sys.exit(1)

    version = input("\nВведите версию (пример: 1.0.76): ").strip()
    if not version:
        print("❌ Версия обязательна")
        sys.exit(1)

    if not update_version_files(version):
        sys.exit(1)

    # Очистка старых сборок
    for d in ["dist", "build"]:
        if os.path.exists(d):
            try:
                shutil.rmtree(d)
                print(f"🧹 Удалена старая папка: {d}")
            except:
                pass

    success = build_onedir()

    clean_temp_files()

    if success:
        print("\n" + "=" * 70)
        print(" ГОТОВО К РАСПРОСТРАНЕНИЮ")
        print(" • Заархивируйте папку dist/DocumentFiller целиком")
        print(" • Пользователь распаковывает → запускает DocumentFiller.exe")
        print(" • Первый запуск: 3–10 сек (часто 4–7)")
        print(" • Последующие запуски: обычно < 3 сек")
        print(" • Совет: добавьте папку в исключения антивируса для ещё большей скорости")
        print("=" * 70)
    else:
        print("\nСборка завершилась с ошибкой.")
        sys.exit(1)


if __name__ == "__main__":
    main()