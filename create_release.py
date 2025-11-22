# create_release.py - скрипт для создания правильных релизов
import os
import shutil
import zipfile
from datetime import datetime


def create_release_package():
    """Создать пакет для релиза с EXE и всеми DLL"""
    print("📦 Создание пакета для релиза...")

    # Папки для сборки
    build_dir = "build_release"
    exe_source_dir = "dist/DocumentFiller"

    if not os.path.exists(exe_source_dir):
        print(f"❌ Папка с EXE не найдена: {exe_source_dir}")
        print("Сначала запустите сборку: python build_complete.py")
        return False

    # Очистка предыдущей сборки
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)

    os.makedirs(build_dir)

    # Копируем EXE и все файлы из папки dist
    print("📄 Копирование EXE и DLL файлов...")
    copied_files = []

    for item in os.listdir(exe_source_dir):
        src_path = os.path.join(exe_source_dir, item)
        dst_path = os.path.join(build_dir, item)

        if os.path.isfile(src_path):
            shutil.copy2(src_path, dst_path)
            copied_files.append(item)
        else:
            shutil.copytree(src_path, dst_path)
            copied_files.append(f"{item}/")

    print(f"✅ Скопировано файлов: {len(copied_files)}")
    for file in copied_files:
        print(f"   - {file}")

    # Создаем ZIP архив
    zip_filename = f"DocumentFiller_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    print(f"🗜️ Создание ZIP архива: {zip_filename}")

    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(build_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, build_dir)
                zipf.write(file_path, arcname)

    # Также копируем отдельный EXE файл для простой установки
    exe_src = os.path.join(exe_source_dir, "DocumentFiller.exe")
    exe_dst = "DocumentFiller.exe"
    if os.path.exists(exe_src):
        shutil.copy2(exe_src, exe_dst)
        print(f"✅ Создан отдельный EXE файл: {exe_dst}")

    print(f"✅ Релизный пакет создан: {zip_filename}")
    print("\n📋 Для публикации релиза:")
    print(f"1. Загрузите {zip_filename} в assets релиза")
    print("2. Загрузите DocumentFiller.exe в assets релиза")
    print("3. Убедитесь, что version_config.json содержит правильную версию")

    return True


if __name__ == "__main__":
    create_release_package()