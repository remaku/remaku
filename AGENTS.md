# AGENTS.md

## Changelog Format

`CHANGELOG.md` uses the following structure:

```markdown
## Version or Unreleased

### Added

### Changed

### Fixed

### Breaking Changes
```

Rules:

- Use `##` headings for versions and `###` headings for categories.
- Only include categories that have content; do not keep empty categories.
- Each item starts with `-` and describes the change in one sentence.
- Write in plain language that end users can understand. Avoid technical jargon (e.g., UIPI, stderr, sink, token). Describe "what the user will experience" rather than "what was technically done."
- Breaking changes must include migration instructions.
- Commit messages use conventional commits format: `feat:`, `fix:`, `refactor:`, `docs:`, `chore:`.

## Code Style

- All `import` statements must be placed at the top of the file. Do not use inline imports inside functions.
- Do not use `_` prefix for naming functions or variables.
  - ❌ `self._current_macro` `def _on_macro_changed()`
  - ✅ `self.current_macro` `def handle_macro_changed()`
- Add a blank line before and after block statements (`if`, `for`, `while`) for readability. Do not add one before `elif`/`else` (they follow the `if` block directly). Consecutive short statements or tightly related logic do not require forced blank lines.

## Git Rules

- **STRICTLY PROHIBITED**: Never execute `git commit` or `git push` on your own under any circumstances. You do not have the authority to commit changes independently.
- **Post-Modification Protocol**: After modifying code, running linters, and completing tests, you must **STOP IMMEDIATELY**. Report the exact files and changes made to the user, and explicitly ask: _"I have completed the modifications. Would you like me to commit these changes now?"_
- **Dependency Updates**: After modifying `pyproject.toml`, run `uv sync` to update the lockfile. Once done, **STOP** and wait for explicit user instructions to commit them together. Do not proceed to commit automatically.

## Development & Build

- **Tech stack**: Python, PySide6 (UI), OpenCV (`cv2` for image recognition), `uv` (package management).
- **Makefile**: A `Makefile` is provided for all common tasks. Run `make` to see available targets.
  - `make setup` — Create venv and install dependencies
  - `make dev` — Run `src/main.py` with hot-reload (requires nodemon)
  - `make lint` — Run `ruff check`
  - `make format` — Run `ruff format`
  - `make format-check` — Check formatting without changes
  - `make typecheck` — Run `pyright`
  - `make test` — Run `pytest` with coverage
  - `make check-all` — Run lint, format-check, typecheck, and test
  - `make build` — Build the installer (PyInstaller + Inno Setup)
  - `make clean` — Remove all build artifacts and caches
