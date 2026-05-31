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
- Every Python file must have a PEP 257-compliant module docstring at the very top (before any `import`) describing the file's purpose.
- Do not use `_` prefix for naming functions or variables.
- Add a blank line before and after block statements (`if`, `for`, `while`) for readability. Do not add one before `elif`/`else` (they follow the `if` block directly). Consecutive short statements or tightly related logic do not require forced blank lines.

## Git Rules

- Never commit or push on your own; always wait for explicit user instruction.
- After modifying `pyproject.toml`, run `uv sync` to update the lockfile, then commit both together.

## Development & Build

- **Tech stack**: Python, PySide6 (UI), OpenCV (`cv2` for image recognition), `uv` (package management).
- **Entry point**: Run `uv run src/main.py` to start the application.
- **Linting & formatting**: Use `ruff`. After modifying code, run `uv run ruff check --fix src` and `uv run ruff format src`.
- **Building the executable**: Run `.\build_exe.ps1` which uses PyInstaller to build the executable and Inno Setup (`iscc`) to package the installer.
