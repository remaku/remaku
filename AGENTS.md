# AGENTS.md

## Changelog Format

`CHANGELOG.md` is multilingual: each version includes sections in English (`<!-- lang:en -->`), Traditional Chinese (`<!-- lang:zh_tw -->`), and Simplified Chinese (`<!-- lang:zh_cn -->`). Category headings use the respective language (e.g., `### Fixed` vs `### 修正` vs `### 修复`).

Rules:

- Use `##` headings for versions and `###` headings for categories.
- Only include categories that have content; do not keep empty categories.
- Each item starts with `-` and describes the change in one sentence.
- Write in plain language that end users can understand. Describe "what the user will experience" rather than "what was technically done."
- Breaking changes must include migration instructions.
- Commit messages use conventional commits format: `feat:`, `fix:`, `refactor:`, `docs:`, `chore:`.

When asked to update the changelog:

1. Check if the latest version in `CHANGELOG.md` has a matching git tag (e.g., `v0.7.0` → `git tag -l "v0.7.0"`).
2. If a tag exists, the version is released — create a new `## Unreleased` section at the top of the file with the three language sub-sections.
3. If no tag exists, add entries to the existing `## Unreleased` section.

## Code Style

- Do not use `_` prefix for naming functions or variables.
- Add a blank line before and after block statements (`if`, `for`, `while`). Do not add one before `elif`/`else`.

## Testing

- Run all tests: `make test`.
- Run a single test file: `uv run pytest tests/path/to/test_file.py`.

## i18n

- Wrap user-visible strings in `self.tr()` or `QCoreApplication.translate()`.
- `make translate` — Update and compile `.ts` / `.qm` files.

## Release Process

When asked to prepare a release:

1. Determine the new version number based on the changes in the Unreleased section.
2. Bump `version` in `pyproject.toml`.
3. Rename `## Unreleased` to `## vX.Y.Z` in `CHANGELOG.md`.
4. Run `uv sync`.
5. Run `make check-all` and fix any issues.
6. Commit with `chore: prepare X.Y.Z release` (only `CHANGELOG.md`, `pyproject.toml`, `uv.lock`).

## Development

- Use `uv run <command>` for all tooling.
- Run `make check-all` before submitting changes (lint, format-check, typecheck, test).
