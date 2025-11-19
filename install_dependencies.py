# install_dependencies.py - установка всех зависимостей
import subprocess
import sys
import os


def install_dependencies():
    print("Установка всех зависимостей для DocumentFiller...")

    dependencies = [
        'PyQt5>=5.15',
        'openpyxl>=3.0',
        'python-docx>=0.8',
        'docxtpl>=0.16',
        'jinja2>=3.0',
        'lxml>=4.6',
        'requests>=2.25',
        'pyinstaller>=5.0'
    ]

    print("Устанавливаемые пакеты:")
    for dep in dependencies:
        print(f"  - {dep}")

    try:
        # Обновляем pip
        subprocess.run([sys.executable, '-m', 'pip', 'install', '--upgrade', 'pip'], check=True)

        # Устанавливаем все зависимости
        for dep in dependencies:
            print(f"Установка {dep}...")
            subprocess.run([sys.executable, '-m', 'pip', 'install', dep], check=True)

        print("\\n✅ Все зависимости успешно установлены!")

        # Проверяем установку
        check_installation()

    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка установки: {e}")
        print("\\nПопробуйте установить вручную:")
        print(f"pip install {' '.join(dependencies)}")


def check_installation():
    """Проверить установку всех модулей"""
    print("\\nПроверка установленных модулей...")

    modules_to_check = [
        'PyQt5', 'openpyxl', 'docx', 'docxtpl',
        'jinja2', 'lxml', 'requests', 'PyInstaller'
    ]

    all_ok = True
    for module in modules_to_check:
        try:
            __import__(module)
            print(f"✅ {module} - OK")
        except ImportError as e:
            print(f"❌ {module} - ОШИБКА: {e}")
            all_ok = False

    if all_ok:
        print("\\n🎉 Все модули успешно установлены!")
        print("Теперь вы можете запустить сборку:")
        print("python build_complete.py")
    else:
        print("\\n⚠️ Некоторые модули не установлены.")
        print("Попробуйте установить их вручную.")


if __name__ == "__main__":
    install_dependencies()