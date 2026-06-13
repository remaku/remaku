# Remaku

An open-source, visual, image-recognition-driven desktop macro tool.

[Download Latest](https://github.com/remaku/remaku/releases/latest/download/Remaku_Setup.exe) · [remaku.com](https://remaku.com) · [Discord](https://discord.gg/MZfks29yTA)

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
- **Status bar** -- shows current step, template name, and total elapsed time after execution
- **Status overlay** -- floating mini status bar on top of fullscreen games with play/stop controls, position remembered and kept within screen bounds
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
| Grid Navigation (grid_nav)                | Step through grid cells in rotation (e.g., inventory menus)                             |

## Step Editing

- **Add steps**: pick from a type menu via the toolbar button or context menu
- **Delete steps**: multi-select deletion supported
- **Copy & paste**: cut/copy/paste steps between macros, template images carried along
- **Move steps**: Alt+Up/Down moves steps, with smart handling for entering, leaving, and crossing block boundaries
- **Wrap in repeat**: wrap selected steps into a repeat block
- **Undo/redo**: 50-step history, Ctrl+Z / Ctrl+Y
- **Skip toggle**: each step can be individually set to skip without deleting
- **Notes**: add optional notes to steps for documentation, shown inline in the step list

## Image Recognition

Template matching uses OpenCV's TM_CCOEFF_NORMED algorithm. If a template is larger than the frame, it is automatically scaled down. The similarity threshold (0--100%) is adjustable in the properties panel.

### Template Management

- Capture a screen region as a template (semi-transparent fullscreen drag-select tool)
- Pick a PNG file from the filesystem as a template
- Template preview in the properties panel
- Capture resolution display: shows width and height at which the template was captured
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

| Item | Description       |
| ---- | ----------------- |
| FPS  | Frames per second |

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
remaku/
  main.py                         # Entry point, initializes config and launches the main window
  paths.py                        # File path utilities
  theme.py                        # Theme management
  version.py                      # Version info (read from pyproject.toml)
  controllers/
    home_controller.py            # Main editor controller (step editing, macro management)
    main_controller.py            # Application-level controller (menus, updates, window)
    pack_explorer_controller.py   # Pack Explorer browse and import logic
    settings_controller.py        # Settings page controller
  core/
    capture.py                    # Screen capture (BetterCam / DXGI)
    dialogs.py                    # Native dialog helpers
    event_bus.py                  # Application-wide event system
    i18n.py                       # Internationalization
    keys.py                       # Keyboard input simulation (pydirectinput)
    vision.py                     # OpenCV image recognition (template matching)
    window.py                     # Windows window management (find, foreground, elevation check)
  models/
    config_model.py               # Configuration data model
    macro_model.py                # Macro data model
    pack_model.py                 # Macro pack catalog model
    step_dict.py                  # Step serialization / deserialization
    step_node.py                  # Step tree node model with parent-child references
    step_tree.py                  # Step tree manager for macro step operations
  resources/
    icon.py                       # SVG icon engine (Lucide icons)
    resources.qrc                 # Qt resource file
    resources_rc.py               # Compiled Qt resources
    icons/                        # SVG icon files
    images/                       # Image assets (logo.png)
    locales/                      # Qt translation files (.ts / .qm)
  services/
    engine.py                     # JSON macro parsing and execution engine
    macro_import_service.py       # Macro import / export (ZIP) logic
    macro_runner.py               # Macro execution runner with threading
    migration.py                  # Legacy data migration
    pack_service.py               # Pack catalog fetching and management
    updater.py                    # Auto-update check and installation
  views/
    home_view.py                  # Main editor view (three-panel layout)
    main_window.py                # Main application window
    pack_explorer_view.py         # Pack Explorer UI
    region_selector.py            # Screen region selection tool
    settings_view.py              # Settings page UI
    components/
      about_dialog.py             # About dialog
      center_panel.py             # Center panel (step tree)
      confirm_dialog.py           # Confirmation dialog
      elided_label.py             # Text elision label widget
      left_panel.py               # Left panel (macro list)
      message_dialog.py           # Message dialog
      new_macro_dialog.py         # New macro dialog
      overlay.py                  # Status overlay floating window
      rename_macro_dialog.py      # Rename macro dialog
      right_panel.py              # Right panel (step properties)
      step_menu.py                # Step type context menu
      template_editor.py          # Template editor widget
      toolbar.py                  # Toolbar with step operations
      update_dialog.py            # Update dialog with release notes
tests/
  controllers/                    # Controller unit tests
  core/                           # Core module unit tests
  models/                         # Model unit tests
  services/                       # Service unit tests
  views/                          # View unit tests
    components/                   # Component unit tests
```

### Quick Start

A `Makefile` is provided. Run `make` to see available targets.

```powershell
make setup        # Create venv and install dependencies
make dev          # Run with hot-reload (requires nodemon)
make test         # Run tests with coverage
make lint         # Run ruff linter
make format       # Run ruff formatter
make format-check # Check formatting without changes
make typecheck    # Run pyright type checker
make check-all    # Run lint, format check, typecheck, and tests
make translate    # Update and compile translation files
make build        # Build the installer (PyInstaller + Inno Setup)
make clean        # Remove all build artifacts and caches
```

## Support

If this tool helps you, consider buying me a coffee

[![GitHub Sponsors](https://img.shields.io/badge/GitHub%20Sponsors-support-ea4aaa?logo=githubsponsors)](https://github.com/sponsors/nelsonlaidev)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-support-yellow?logo=buymeacoffee)](https://buymeacoffee.com/nelsonlaidev)

## License

[AGPL-3.0](LICENSE)
