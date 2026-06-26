# Remaku

An open-source, visual, image-recognition-driven desktop macro tool.

[Download Latest](https://github.com/remaku/remaku/releases/latest/download/Remaku_Setup.exe) · [remaku.com](https://remaku.com) · [Discord](https://discord.gg/MZfks29yTA)

[繁體中文](README_zh-TW.md) | [简体中文](README_zh-CN.md)

## Installation Notes

On first run, Windows SmartScreen may show a "Windows protected your PC" warning. Click "More info" then "Run anyway" to proceed.

This warning is harmless. It appears because the executable is not code-signed. This project is open-source software; code-signing certificates cost $200+ per year and are not currently used.

## Features

- **No coding required** -- list-based UI for composing actions from 15 step types, with drag-and-drop reordering and context menus
- **Image recognition driven** -- capture screenshots as templates, match against the screen to decide when to act
- **Number recognition** -- capture a screen area containing a number and branch, wait, or repeat based on the value
- **Lightweight single exe** -- no extra runtime environment needed
- **Open source** -- fully public source code, auditable and community-contributable
- **JSON workflow format** -- import/export as ZIP, ready to share with the community
- **Global hotkeys** -- assign independent hotkeys to each macro for one-key activation
- **Keyboard and mouse automation** -- send key combinations, type Unicode text, click, move, and scroll
- **Branch-friendly editor** -- nested steps and branches are shown in a tree, with direct add buttons inside branches
- **Status bar** -- shows current step, template name, and total elapsed time after execution
- **Status overlay** -- floating mini status bar on top of fullscreen games with play/stop controls, position remembered and kept within screen bounds
- **Macro recording** -- record keyboard and mouse actions from outside the app into macro steps
- **Macro variables** -- define reusable variables for step properties so you can change a value once and update every step that uses it
- **Auto update** -- checks GitHub Releases on startup, supports stable and beta channels
- **Macro Explorer** -- browse official macro packs and import compatible macros from inside the app

## Supported Step Types

| Type                                      | Description                                                                                           |
| ----------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| Key (key)                                 | Press a specified key or modifier combination, with configurable hold duration                        |
| Text Input (text_input)                   | Type custom Unicode text, with an optional delay between characters                                   |
| Mouse Click (mouse_click)                 | Click at a coordinate or on a matched template                                                        |
| Mouse Move (mouse_move)                   | Move the cursor to a coordinate or to a matched template                                              |
| Mouse Scroll (mouse_scroll)               | Scroll the mouse wheel by a specified number of clicks                                                |
| Delay (delay)                             | A fixed millisecond pause                                                                             |
| Wait Image (wait_image)                   | Wait for a template image to appear, with configurable similarity threshold, timeout, and next action |
| Wait Number (wait_number)                 | Wait until a visible number in a captured screen area reaches a target value                          |
| Wait Any Image (if_any_image)             | Monitor multiple templates simultaneously, execute the matching branch                                |
| Conditional Branch (if_image)             | Execute then or else path depending on whether the template appears                                   |
| Conditional Branch (if_number)            | Branch based on a number in a captured screen area                                                    |
| Repeat Loop (repeat)                      | Repeat child steps N times                                                                            |
| Repeat Until Number (repeat_until_number) | Repeat child steps until a visible number reaches a target value                                      |
| Hold Key Until Gone (hold_key_until_gone) | Hold a key until the template image disappears                                                        |
| Grid Navigation (grid_nav)                | Step through grid cells in rotation (e.g., inventory menus)                                           |

## Step Editing

- **Add steps**: pick from a type menu via the toolbar button or context menu
- **Delete steps**: multi-select deletion supported
- **Copy & paste**: cut/copy/paste steps between macros, template images carried along
- **Move steps**: Alt+Up/Down moves steps, with smart handling for entering, leaving, and crossing block boundaries
- **Wrap in repeat**: wrap selected steps into a repeat block
- **Branch editing**: then/else, template, and grid-navigation branches have their own details panel and add button
- **Tree view**: nested steps and branches can be expanded or collapsed for easier navigation
- **Undo/redo**: 50-step history, Ctrl+Z / Ctrl+Y
- **Skip toggle**: each step can be individually set to skip without deleting
- **Notes**: add optional notes to steps for documentation, shown inline in the step list

## Image Recognition

Template matching uses OpenCV's TM_CCOEFF_NORMED algorithm. If a template is larger than the frame, it is automatically scaled down when Gaming Mode is enabled. Turn Gaming Mode off for desktop automation where the window size stays the same. The similarity threshold (0--100%) is adjustable in the properties panel, and color mode can be enabled when distinct colors matter.

Number recognition reads visible numbers in a captured screen area, enabling steps like Wait Number, If Number, and Repeat Until Number.

### Template Management

- Capture a screen region as a template (semi-transparent fullscreen drag-select tool)
- Pick a PNG file from the filesystem as a template
- Template preview in the properties panel
- Capture resolution display: shows width and height at which the template was captured
- Optional color matching for templates with visually distinct colors
- Rename and delete templates
- Templates are stored alongside macros and bundled on export

## Window Management

- Auto-find target window by title, with partial matching
- Dropdown listing all visible windows for easy selection, plus "(Use foreground window)" to target whatever is active
- Captures the client area (excluding borders and title bar)
- Background capture and input: keeps running against the selected target window without requiring focus
- Per-macro options can switch between background input and regular input, and can send focus-like messages to the target window to help prevent some apps from pausing
- Automatically re-finds the target window if it is closed and reopened during macro execution
- Elevation mismatch warning: warns if the target window runs as administrator while Remaku does not (UIPI blocks SendInput)
- Multi-display aware: overlays and selectors appear on the correct monitor

## Settings

### Macro

| Item               | Description                                                                                |
| ------------------ | ------------------------------------------------------------------------------------------ |
| Target             | The window title Remaku should find before running the macro                               |
| Hotkey             | Independent global hotkey for this macro                                                   |
| Gaming Mode        | Enable template scaling for games; turn it off for fixed-size desktop automation workflows |
| Background Input   | Send input directly to the target window without switching focus                           |
| Prevent Focus Loss | Send periodic focus signals to the target window to prevent apps from pausing              |

### General

| Item                    | Description                                                   |
| ----------------------- | ------------------------------------------------------------- |
| Always on Top           | Keep Remaku above all other windows                           |
| Show Status Overlay     | Display a transparent overlay showing macro execution status  |
| Check Update on Startup | Auto-check GitHub Releases at launch                          |
| Update Channel          | stable or beta                                                |
| Theme                   | System, Light, Dark                                           |
| Language                | Auto-detect, Traditional Chinese, Simplified Chinese, English |
| Pause/Resume Hotkey     | Global hotkey to pause or resume the current macro            |

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

## Macro Packs

- Open Macro Explorer from the File menu
- Browse official macro packs from inside Remaku
- Import compatible macros directly into your local macro folder

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

## Contributing

See the [Contributing Guide](https://remaku.com/docs/contributing) for development setup and contribution guidelines.

## Support

If this tool helps you, consider buying me a coffee

[![GitHub Sponsors](https://img.shields.io/badge/GitHub%20Sponsors-support-ea4aaa?logo=githubsponsors)](https://github.com/sponsors/nelsonlaidev)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-support-yellow?logo=buymeacoffee)](https://buymeacoffee.com/nelsonlaidev)

## License

[AGPL-3.0](LICENSE)
