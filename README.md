# Remaku

An open-source, visual, image-recognition-driven desktop macro tool.

[Download Latest](https://github.com/remaku/remaku/releases/latest/download/Remaku_Setup.exe) · [remaku.com](https://remaku.com) · [Discord](https://discord.gg/ncK4mhPkwt)

[繁體中文](README_zh-TW.md) | [简体中文](README_zh-CN.md)

## Installation Notes

On first run, Windows SmartScreen may show a "Windows protected your PC" warning. Click "More info" then "Run anyway" to proceed.

This warning is harmless. It appears because the executable is not code-signed. This project is open-source software; code-signing certificates cost $200+ per year and are not currently used.

## Features

- **No coding required** -- list-based UI for composing actions, with drag-and-drop reordering and context menus
- **Image recognition driven** -- capture screenshots as templates, match against the screen to decide when to act
- **Lightweight single exe** -- no extra runtime environment needed
- **Open source** -- fully public source code, auditable and community-contributable
- **JSON workflow format** -- import/export as ZIP, ready to share with the community
- **Global hotkeys** -- assign independent hotkeys to each macro for one-key activation
- **Auto update** -- checks GitHub Releases on startup, supports stable and beta channels

## Supported Step Types

| Type                                      | Description                                                                             |
| ----------------------------------------- | --------------------------------------------------------------------------------------- |
| Key (key)                                 | Press a specified key with configurable hold duration                                   |
| Delay (delay)                             | A fixed millisecond pause                                                               |
| Wait Image (wait_image)                   | Wait for a template image to appear, with configurable similarity threshold and timeout |
| Wait Any Image (if_any_image)             | Monitor multiple templates simultaneously, execute the matching branch                  |
| Conditional Branch (if_image)             | Execute then or else path depending on whether the template appears                     |
| Repeat Loop (repeat)                      | Repeat child steps N times                                                              |
| Hold Key Until Gone (hold_key_until_gone) | Hold a key until the template image disappears                                          |
| Foreground Check (foreground)             | Wait for the target window to come to the foreground                                    |
| Grid Navigation (grid_nav)                | Step through grid cells in rotation (e.g., inventory menus)                             |

## Step Editing

- **Add steps**: pick from a type menu via the toolbar button or context menu
- **Delete steps**: multi-select deletion supported
- **Copy & paste**: cut/copy/paste steps between macros, template images carried along
- **Move steps**: Alt+Up/Down moves steps, with smart handling for entering, leaving, and crossing block boundaries
- **Wrap in repeat**: wrap selected steps into a repeat block
- **Undo/redo**: 50-step history, Ctrl+Z / Ctrl+Y
- **Skip toggle**: each step can be individually set to skip without deleting

## Image Recognition

Template matching uses OpenCV's TM_CCOEFF_NORMED algorithm. If a template is larger than the frame, it is automatically scaled down. The similarity threshold (0--100%) is adjustable in the properties panel.

### Template Management

- Capture a screen region as a template (semi-transparent fullscreen drag-select tool)
- Pick a PNG file from the filesystem as a template
- Template preview in the properties panel
- Rename and delete templates
- Templates are stored alongside macros and bundled on export

## Window Management

- Auto-find target window by title, with partial matching
- Dropdown listing all visible windows for easy selection
- Captures the client area (excluding borders and title bar)
- Foreground detection: auto-waits when not in foreground
- Elevation mismatch warning: warns if the target window runs as administrator while Remaku does not (UIPI blocks SendInput)

## Settings

### General

| Item                    | Description                                                   |
| ----------------------- | ------------------------------------------------------------- |
| Always on Top           | Keep Remaku above all other windows                           |
| Check Update on Startup | Auto-check GitHub Releases at launch                          |
| Update Channel          | stable or beta                                                |
| Theme                   | System, Light, Dark                                           |
| Language                | Auto-detect, Traditional Chinese, Simplified Chinese, English |

### Capture

| Item    | Description             |
| ------- | ----------------------- |
| FPS     | Frames per second       |

### Input

| Item        | Description                                                               |
| ----------- | ------------------------------------------------------------------------- |
| Jitter (ms) | Random delay range added to each keypress (ms), helps avoid bot detection |

### Other

- Shows the currently skipped update version, with a one-click clear to re-prompt

## Auto Update

- Checks the latest GitHub Release via the API
- Update dialog shows release notes (Markdown)
- Inline download with progress bar
- One-click silent install: downloads the installer, launches it with `/VERYSILENT`, then quits Remaku; the new version auto-starts after installation
- "Skip this version" to suppress the prompt for that release

## Keyboard Shortcuts

| Shortcut     | Action                |
| ------------ | --------------------- |
| Ctrl+N       | New macro             |
| Ctrl+,       | Open settings         |
| Ctrl+Shift+N | Add step              |
| Delete       | Delete selected steps |
| Alt+Up       | Move step up          |
| Alt+Down     | Move step down        |
| Ctrl+Z       | Undo                  |
| Ctrl+Y       | Redo                  |
| Ctrl+D       | Duplicate steps       |
| Ctrl+C       | Copy                  |
| Ctrl+X       | Cut                   |
| Ctrl+V       | Paste                 |

## File Locations

All macros, templates, and settings are stored under `Documents\remaku\`:

```
Documents\remaku\
  config.json        # Application settings
  macros\            # Macro JSON files
    1680000000.json
  templates\         # Template PNG images
    <macro_name>\
      1680000001.png
  logs\              # Execution logs
    remaku.log
```

## Development

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/). GUI uses PySide6 (Qt6) and qfluentwidgets.

### Project Structure

```
src/
  main.py              # Entry point, initializes config and launches the main window
  main_window.py       # Main window: three-panel layout, menus, step editing
  runner.py            # Step runner base class, manages threads and status
  macro_engine.py      # JSON macro parsing and execution engine
  vision.py            # OpenCV image recognition (template matching)
  capture.py           # Screen capture (BetterCam / DXGI)
  keys.py              # Keyboard input simulation (pydirectinput)
  window.py            # Windows window management (find, foreground, elevation check)
  region_selector.py   # Screen region selection tool
  config.py            # Configuration file read/write
  settings.py          # Settings page UI
  updater.py           # Auto-update check and installation
  version.py           # Version info (read from pyproject.toml)
  icons.py             # SVG icon engine (Lucide icons)
  i18n/                # Internationalization translation files
    __init__.py
    zh_tw.json
    zh_cn.json
    en.json
```

### Run from Source

```powershell
uv sync
uv run src/main.py
```

### Lint and Format

```powershell
uv run ruff check --fix src
uv run ruff format src
```

### Build .exe

```powershell
.\build_exe.ps1
```

The build process uses PyInstaller to create a single executable, then Inno Setup (`iscc`) to produce the installer.

## Support

If this tool helps you, consider buying me a coffee

[![GitHub Sponsors](https://img.shields.io/badge/GitHub%20Sponsors-support-ea4aaa?logo=githubsponsors)](https://github.com/sponsors/nelsonlaidev)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-support-yellow?logo=buymeacoffee)](https://buymeacoffee.com/nelsonlaidev)

## License

[AGPL-3.0](LICENSE)
