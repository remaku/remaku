SHELL := pwsh.exe
.SHELLFLAGS := -NoProfile -Command

TS_DIR := .\remaku\resources\locales
TS_FILES := $(TS_DIR)\zh_TW.ts $(TS_DIR)\zh_CN.ts
TAG ?= v0.1.0

.PHONY: setup sync clean lint format format-check typecheck test check-all lupdate lrelease translate dev build release-note

setup:
	@uv venv
	@uv sync

sync:
	@uv sync

clean:
	@if (Test-Path .pytest_cache) { Remove-Item -Recurse -Force .pytest_cache }
	@if (Test-Path .ruff_cache) { Remove-Item -Recurse -Force .ruff_cache }
	@if (Test-Path .venv) { Remove-Item -Recurse -Force .venv }
	@if (Test-Path build) { Remove-Item -Recurse -Force build }
	@if (Test-Path dist) { Remove-Item -Recurse -Force dist }
	@if (Test-Path htmlcov) { Remove-Item -Recurse -Force htmlcov }
	@if (Test-Path output) { Remove-Item -Recurse -Force output }
	@if (Test-Path .coverage) { Remove-Item -Recurse -Force .coverage }
	@if (Test-Path RELEASE_BODY.md) { Remove-Item -Recurse -Force RELEASE_BODY.md }
	@if (Test-Path Remaku.spec) { Remove-Item -Recurse -Force Remaku.spec }
	@if (Test-Path version_info.txt) { Remove-Item -Recurse -Force version_info.txt }
	@Get-ChildItem -Include __pycache__,*.pyc -Recurse | Remove-Item -Recurse -Force

lint:
	@uv run ruff check

format:
	@uv run ruff format

format-check:
	@uv run ruff format --check

typecheck:
	@uv run pyright

test:
	@uv run pytest --cov=remaku --cov-report=term-missing

check-all: lint format-check typecheck test

lupdate:
	@pwsh -File .\scripts\lupdate.ps1 -TsFilesRaw "$(TS_FILES)"

lrelease:
	@pwsh -File .\scripts\lrelease.ps1 -TsFilesRaw "$(TS_FILES)" -TsDir "$(TS_DIR)"

translate: lupdate lrelease

dev:
	@nodemon --watch remaku --ext py --exec "uv run main.py"

build:
	@pwsh -File .\scripts\build.ps1

release-note:
	@pwsh -File .\scripts\release-note.ps1 -TagName "$(TAG)"