# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('version_config.json', '.'), ('repo_config.json', '.'), ('Шаблоны', 'Шаблоны')
    ],
    hiddenimports=[
        # Основные модули приложения
        'main_window', 'settings', 'theme_manager', 
        'license_manager', 'update_manager', 'widgets',

        # PyQt5 модули
        'PyQt5', 'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets', 'PyQt5.QtNetwork',
        'PyQt5.sip',

        # Документы и шаблоны
        'openpyxl', 'docxtpl', 'jinja2', 'docx',
        'lxml', 'lxml.etree', 'lxml._elementpath',

        # Сеть - ВАЖНО: включаем все необходимые модули для requests
        'requests', 'urllib3', 'chardet', 'idna', 'certifi',
        'email', 'email.mime', 'email.mime.text', 'email.mime.multipart',
        'email.mime.base', 'email.encoders', 'email.utils',
        'ssl', 'http', 'http.client', 'http.cookies',

        # Системные модули которые нужны для работы
        'hashlib', 'json', 'datetime', 'os', 'sys', 're',
        'uuid', 'platform', 'threading', 'tempfile', 'zipfile',
        'xml', 'xml.etree', 'xml.etree.ElementTree'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Исключаем только действительно ненужные модули
        'tkinter', 'unittest', 'test', 'pydoc',
        'numpy', 'pandas', 'scipy', 'matplotlib', 'PIL',
        'pygame', 'wx', 'gtk', 'curses',
        'concurrent', 'distutils', 'setuptools',
        'pip', 'wheel', 'pkg_resources', 'notebook',
        'jupyter', 'ipython', 'qtpy', 'pyqtgraph'
    ],
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
