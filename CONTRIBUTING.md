# Contributing to Codex Mate

Thanks for helping improve Codex Mate. This project is a local companion
launcher and maintenance toolkit for the Codex desktop app, so changes should
stay careful, reversible, and easy to diagnose.

## Development Setup

1. Install Python 3.11 or newer.
2. Create and activate a virtual environment.
3. Install the project in editable mode:

```bash
python -m pip install -e ".[test]"
```

4. Run the test suite:

```bash
pytest -q
```

## Contribution Guidelines

- Keep changes scoped to one behavior or platform flow at a time.
- Do not modify the installed Codex App bundle. Codex Mate should keep working
  through external launchers, Chrome DevTools Protocol injection, local helper
  APIs, and local configuration/state repair.
- Preserve user escape hatches such as `launch --no-history-sync`.
- Prefer read-only checks before writing local Codex state.
- Add or update focused tests when changing launch, watcher, installer,
  updater, injection, helper, or history-sync behavior.
- Keep Windows and macOS behavior aligned where practical, while respecting
  each platform's launcher and permission model.

## Pull Request Checklist

- `pytest -q` passes locally.
- New or changed user-facing behavior is documented in `README.md`.
- Changes that write local Codex state include a clear condition check and a
  backup or rollback path where appropriate.
- Platform-specific changes mention the tested platform and any known gaps.

## Release Notes

Release changes should bump both `codex_mate/__init__.py` and
`pyproject.toml`, update the README when needed, and publish release assets
through the GitHub Actions release workflow.
