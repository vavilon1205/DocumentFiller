
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('анкеты_данные.xlsx', '.'),
        ('Личные карточки.docx', '.'),
        ('Согласи Кишалов.docx', '.'),
        ('Согласие в Россгвардию.docx', '.'),
        ('Согласие Зотов.docx', '.'),
        ('Согласие Кишалов.docx', '.'),
        ('Согласие Ковех.docx', '.'),
        ('Согласие Корпачев.docx', '.'),
        ('Согласие Премьер Саттелит.docx', '.'),
        ('Согласие ТРАНСБЕЗОПАСНОСТЬ.docx', '.'),
        ('Согласие Труфанов.docx', '.'),
        ('Согласие Фалькон.docx', '.'),
        ('Согласие Финкин.docx', '.'),
        ('Согласие Шишкин.docx', '.'),
        ('repo_config.json', '.'),
        ('version.py', '.')
    ],
    hiddenimports=[
        'main_window', 'settings', 'theme_manager', 
        'license_manager', 'update_manager', 'widgets', 'version',
        'PyQt5', 'docxtpl', 'openpyxl'
    ],
    noarchive=False
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    [],
    name='DocumentFiller',
    console=False,
    icon=None
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    a.zipfiles,
    strip=False,
    upx=True,
    name='DocumentFiller'
)
