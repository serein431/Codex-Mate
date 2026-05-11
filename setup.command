#!/bin/sh
set -eu

cd "$(dirname "$0")"
CODEX_MATE_BIN="./CodexMate"

clear
printf '%s\n' '========================================'
printf '%s\n' '             Codex Mate Setup'
printf '%s\n' '========================================'
printf '\n'
printf '%s\n' '[1] Install Codex Mate'
printf '%s\n' '[2] Uninstall Codex Mate'
printf '%s\n' '[3] Update Codex Mate'
printf '%s\n' '[4] Exit'
printf '\n'
printf '%s' 'Please select an option [1-4]: '
read choice

find_python() {
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return
  fi
  if command -v python >/dev/null 2>&1; then
    command -v python
    return
  fi
  return 1
}

PYTHON_BIN="$(find_python || true)"

run_codex_mate() {
  if [ -x "$CODEX_MATE_BIN" ]; then
    "$CODEX_MATE_BIN" "$@"
    return
  fi
  if [ -n "${PYTHON_BIN}" ]; then
    "$PYTHON_BIN" -m codex_mate "$@"
    return
  fi
  printf '\n%s\n' 'Python was not found and the bundled CodexMate executable is not in this folder.'
  printf '%s\n' 'Download CodexMate-macos.zip from the latest GitHub Release, unzip it, then run setup.command again.'
  printf '\n%s' 'Press Enter to close...'
  read _
  exit 1
}

run_install() {
  if [ ! -x "$CODEX_MATE_BIN" ]; then
    if [ -z "${PYTHON_BIN}" ]; then
      run_codex_mate setup
    fi
    printf '\n%s\n' 'Installing Python package...'
    "$PYTHON_BIN" -m pip install -e .
  else
    printf '\n%s\n' 'Using bundled CodexMate executable.'
  fi
  printf '\n%s\n' 'Installing Codex Mate app, LaunchAgent, and transparent watcher...'
  run_codex_mate setup
  printf '\n%s\n' 'Codex Mate installed successfully.'
  printf '%s\n' 'You can keep launching Codex from your normal entry point; Codex Mate will take over automatically.'
}

run_uninstall() {
  printf '\n%s\n' 'Uninstalling Codex Mate app, LaunchAgent, and transparent watcher...'
  run_codex_mate remove
  printf '\n%s\n' 'Codex Mate uninstalled successfully.'
}

run_update() {
  printf '\n%s\n' 'Updating Codex Mate from GitHub Release...'
  if [ -x "$CODEX_MATE_BIN" ]; then
    printf '%s\n' 'Bundled executable installs are updated by downloading the latest CodexMate-macos.zip and running setup.command again.'
  else
    run_codex_mate update
    printf '\n%s\n' 'Codex Mate update finished.'
  fi
}

case "$choice" in
  1) run_install ;;
  2) run_uninstall ;;
  3) run_update ;;
  4) exit 0 ;;
  *)
    printf '\n%s\n' 'Invalid choice.'
    printf '\n%s' 'Press Enter to close...'
    read _
    exit 1
    ;;
esac

printf '\n%s' 'Press Enter to close...'
read _
