# bootstrap.py - ИСПРАВЛЕННАЯ ВЕРСИЯ С ПОИСКОМ АРХИВА ВНУТРИ EXE
import os
import sys
import subprocess
import zipfile
import shutil
import logging
from datetime import datetime
import ctypes

def show_error(msg):
    """Показать сообщение об ошибке через MessageBox"""
    ctypes.windll.user32.MessageBoxW(0, msg, "Ошибка загрузчика", 0)

def setup_logging():
    """Настроить логирование в файл bootstrap.log"""
    log_file = os.path.join(os.path.dirname(sys.executable), "bootstrap.log")
    logging.basicConfig(
        filename=log_file,
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        encoding='utf-8'
    )
    logging.info("="*50)
    logging.info(f"Запуск загрузчика. Версия Python: {sys.version}")
    logging.info(f"Путь к exe: {sys.executable}")
    logging.info(f"Аргументы: {sys.argv}")
    return log_file

def get_base_path():
    """Получить базовый путь для поиска файлов (учитывая скомпилированное состояние)"""
    if getattr(sys, 'frozen', False):
        # Если скомпилировано PyInstaller, данные лежат в sys._MEIPASS
        return sys._MEIPASS
    else:
        # При разработке - рядом с exe
        return os.path.dirname(sys.executable)

def get_internal_dir():
    """Возвращает путь к папке, где будут храниться распакованные файлы программы."""
    return os.path.join(os.path.dirname(sys.executable), "_internal")

def is_extracted():
    """Проверяет, были ли уже распакованы файлы (по наличию маркера)."""
    marker = os.path.join(get_internal_dir(), ".extracted")
    return os.path.exists(marker)

def extract_files():
    """Распаковывает встроенный архив bootstrap.zip во внутреннюю папку."""
    internal_dir = get_internal_dir()
    logging.info(f"Первоначальная распаковка в {internal_dir}")
    os.makedirs(internal_dir, exist_ok=True)

    # Путь к архиву (в зависимости от того, скомпилировано или нет)
    base_path = get_base_path()
    archive_path = os.path.join(base_path, "bootstrap.zip")
    logging.info(f"Поиск архива: {archive_path}")

    if not os.path.exists(archive_path):
        # Если архива нет (при разработке) – используем папку dist/Программа (только для отладки)
        dev_path = os.path.join(os.path.dirname(sys.executable), "..", "dist", "Программа")
        if os.path.exists(dev_path):
            logging.info(f"Архив не найден, копируем из {dev_path}")
            shutil.copytree(dev_path, internal_dir, dirs_exist_ok=True)
        else:
            error_msg = f"Не найден архив bootstrap.zip или папка с программой.\nПуть: {archive_path}"
            logging.error(error_msg)
            show_error(error_msg)
            sys.exit(1)
    else:
        logging.info(f"Архив найден, распаковка...")
        try:
            with zipfile.ZipFile(archive_path, 'r') as zf:
                zf.extractall(internal_dir)
            logging.info("Распаковка завершена.")
        except Exception as e:
            error_msg = f"Ошибка распаковки архива: {str(e)}"
            logging.error(error_msg)
            show_error(error_msg)
            sys.exit(1)

    # Создаём маркер
    with open(os.path.join(internal_dir, ".extracted"), 'w') as f:
        f.write("extracted")
    logging.info("Маркер .extracted создан.")

def main():
    log_file = setup_logging()
    try:
        if not is_extracted():
            extract_files()

        internal_dir = get_internal_dir()
        main_exe = os.path.join(internal_dir, "Программа.exe")
        logging.info(f"Запуск основной программы: {main_exe}")

        if not os.path.exists(main_exe):
            error_msg = f"Не найден основной исполняемый файл: {main_exe}"
            logging.error(error_msg)
            show_error(error_msg)
            return

        # Запускаем основную программу
        logging.info(f"Запуск: {main_exe} с аргументами {sys.argv[1:]}")
        result = subprocess.run([main_exe] + sys.argv[1:])
        logging.info(f"Основная программа завершилась с кодом {result.returncode}")
    except Exception as e:
        error_msg = f"Необработанная ошибка: {str(e)}"
        logging.exception(error_msg)
        show_error(error_msg)

if __name__ == "__main__":
    main()