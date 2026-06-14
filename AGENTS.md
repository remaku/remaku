# AGENTS.md

## Project Structure

```
remaku/                   # Main package (NOT src/)
├── controllers/          # Application controllers
├── core/                 # Core functionality (window, vision, keys, i18n, dialogs, capture)
├── models/               # Data models (config, macro, step node/tree)
├── resources/            # Static assets (images, translation .ts/.qm files)
├── services/             # Macro runner, pack service, import, updater, migration
├── views/                # UI views with components/ subdirectory
├── paths.py              # Path utilities
├── theme.py              # Fluent theme configuration
└── version.py            # Version info
main.py                   # Entry point
tests/                    # Unit and integration tests (mirrors package structure)
```

## Changelog Format

`CHANGELOG.md` is multilingual: each version includes sections in English (`<!-- lang:en -->`), Traditional Chinese (`<!-- lang:zh_tw -->`), and Simplified Chinese (`<!-- lang:zh_cn -->`). Category headings use the respective language (e.g., `### Fixed` vs `### 修正` vs `### 修复`).

Rules:

- Use `##` headings for versions and `###` headings for categories.
- Only include categories that have content; do not keep empty categories.
- Each item starts with `-` and describes the change in one sentence.
- Write in plain language that end users can understand. Avoid technical jargon (e.g., UIPI, stderr, sink, token). Describe "what the user will experience" rather than "what was technically done."
- Breaking changes must include migration instructions.
- Commit messages use conventional commits format: `feat:`, `fix:`, `refactor:`, `docs:`, `chore:`.

## Code Style

- All `import` statements must be placed at the top of the file. Do not use inline imports inside functions.
- Imports follow isort convention (enforced by ruff `I` rule): standard library, third-party, local modules, each group separated by a blank line.
- Maximum line length is 120 characters (configured in ruff).
- Do not use `_` prefix for naming functions or variables.
  - ❌ `self._current_macro` `def _on_macro_changed()`
  - ✅ `self.current_macro` `def handle_macro_changed()`
- Add a blank line before and after block statements (`if`, `for`, `while`) for readability. Do not add one before `elif`/`else` (they follow the `if` block directly). Consecutive short statements or tightly related logic do not require forced blank lines.

## Testing

- Tests live in `tests/` and mirror the package structure (e.g., `remaku/core/vision.py` → `tests/core/test_vision.py`).
- Use `pytest` with `pytest-qt` for GUI tests and `pytest-cov` for coverage.
- Run all tests: `make test`.
- Run a single test file: `uv run pytest tests/path/to/test_file.py`.
- Test files are named `test_<module>.py`. Test functions are named `test_<behavior>`.

## i18n / Localization

- UI translations use Qt `.ts` files in `remaku/resources/locales/`.
- `make lupdate` — Extract translatable strings from source code.
- `make lrelease` — Compile `.ts` files to `.qm` binaries.
- `make translate` — Run both lupdate and lrelease.
- When adding user-visible strings, wrap them in `self.tr()` or `QCoreApplication.translate()`.

## Release Process

When the user asks to prepare a release (e.g., "prepare for new stable release"):

1. Determine the new version number based on the changes in the Unreleased section.
2. Bump `version` in `pyproject.toml`.
3. Rename `## Unreleased` to `## vX.Y.Z` in `CHANGELOG.md`.
4. Run `uv sync` to update `uv.lock`.
5. Run `make check-all` (lint, format-check, typecheck, test) and fix any issues.
6. Commit the release with the message: `chore: prepare X.Y.Z release`
   - The commit must include only `CHANGELOG.md`, `pyproject.toml`, and `uv.lock`.

## Development & Build

- **Tech stack**: Python 3.12, PySide6 + PySide6-Fluent-Widgets (UI), OpenCV (`cv2` for image recognition), `loguru` (logging), `uv` (package management).
- **Package manager**: Use `uv run <command>` to execute tools within the project virtual environment.
- **Makefile**: A `Makefile` is provided for all common tasks. Run `make` to see available targets.
  - `make setup` — Create venv and install dependencies
  - `make sync` — Update dependencies and lockfile
  - `make dev` — Run `main.py` with hot-reload (requires nodemon)
  - `make lint` — Run `ruff check`
  - `make format` — Run `ruff format`
  - `make format-check` — Check formatting without changes
  - `make typecheck` — Run `pyright`
  - `make test` — Run `pytest` with coverage
  - `make check-all` — Run lint, format-check, typecheck, and test (recommended before submitting changes)
  - `make translate` — Update and compile Qt translations
  - `make build` — Build the installer (PyInstaller + Inno Setup)
  - `make clean` — Remove all build artifacts and caches
- **Pre-commit**: Run `uv run pre-commit run --all-files` to check staged files before committing.
