$ErrorActionPreference = "Stop"

uv sync --group dev

$v = uv run python -c "import re; from pathlib import Path; print(re.search(r'version\s*=\s*\`"(.+?)\`"', Path('pyproject.toml').read_text()).group(1))"
$numericV = $v -replace '-.*', ''

uv run python -c @"
from pathlib import Path
v = '$v'
p = ('$numericV'.split('.') + ['0']*4)[:4]
Path('version_info.txt').write_text(f'''VSVersionInfo(
  ffi=FixedFileInfo(filevers=({p[0]},{p[1]},{p[2]},{p[3]}),prodvers=({p[0]},{p[1]},{p[2]},{p[3]})),
  kids=[
    StringFileInfo([StringTable('040904B0',[
      StringStruct('FileDescription','Remaku'),
      StringStruct('FileVersion','{v}'),
      StringStruct('ProductName','Remaku'),
      StringStruct('ProductVersion','{v}'),
      StringStruct('CompanyName','nelsonlaidev'),
      StringStruct('LegalCopyright','AGPL-3.0'),
    ])]),
    VarFileInfo([VarStruct('Translation',[0x0409,1200])])
  ]
)''')
"@

uv run python -m PyInstaller `
  --noconfirm `
  --clean `
  --onedir `
  --windowed `
  --name Remaku `
  --icon icon.ico `
  --manifest Remaku.manifest `
  --add-data "icon.ico;." `
  --add-data "src/icons;icons" `
  --add-data "src/i18n;i18n" `
  --add-data "pyproject.toml;." `
  --version-file version_info.txt `
  --paths src `
  --hidden-import win32api `
  --hidden-import win32gui `
  --exclude-module tkinter `
  --exclude-module PyQt5 `
  --exclude-module PyQt6 `
  src/main.py

iscc /DMyAppVersion="$numericV" installer.iss
