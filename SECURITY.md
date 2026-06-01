# Security Policy

Codex Mate interacts with local Codex configuration, local history files,
SQLite state, launcher shortcuts, and helper-server endpoints. Please report
security-sensitive issues privately instead of opening a public issue.

## Reporting a Vulnerability

If you find a vulnerability, please email the maintainer or contact the
repository owner on GitHub with:

- A short description of the issue.
- Steps to reproduce it.
- The affected operating system and Codex Mate version.
- Whether the issue can modify local Codex state, expose local files, or run
  unintended commands.

Please do not include private tokens, API keys, or personal Codex history in
the report. Redacted logs are preferred.

## Scope

Security reports are especially useful for:

- Local helper-server endpoints.
- Chrome DevTools Protocol injection behavior.
- Installer, updater, watcher, and launcher flows.
- History sync and rollback behavior.
- Handling of local Codex auth, provider, model, and session state.

## Project Boundaries

Codex Mate does not modify the installed Codex App bundle and should not
replace `app.asar` or other application files. Enhancements should remain
external, inspectable, and reversible.
