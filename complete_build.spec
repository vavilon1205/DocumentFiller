# -*- mode: python ; coding: utf-8 -*-
# Оптимизированная сборка DocumentFiller

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('version_config.json', '.'), ('repo_config.json', '.')
    ],
    hiddenimports=['main_window', 'settings', 'theme_manager', 'license_manager', 'update_manager', 'widgets', 'PyQt5', 'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets', 'PyQt5.QtNetwork', 'PyQt5.sip', 'openpyxl', 'docxtpl', 'jinja2', 'docx', 'lxml', 'lxml.etree', 'lxml._elementpath', 'requests', 'urllib3', 'chardet', 'idna', 'certifi', 'hashlib', 'json', 'datetime', 'os', 'sys', 're', 'uuid', 'platform', 'threading', 'tempfile', 'zipfile'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'test', 'pydoc', 'email', 'numpy', 'pandas', 'scipy', 'matplotlib', 'PIL', 'pygame', 'wx', 'gtk', 'curses', 'multiprocessing', 'concurrent', 'html', 'http', 'xmlrpc', 'ssl', 'asyncio', 'selectors', 'distutils', 'setuptools', 'pip', 'wheel', 'pkg_resources', 'notebook', 'jupyter', 'ipython', 'qtpy', 'pyqtgraph'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
    optimize=2,  # Максимальная оптимизация
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
    upx=True,  # Сжатие исполняемых файлов
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Без консоли
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
