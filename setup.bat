@echo off
setlocal
cd /d "%~dp0"

:menu
cls
echo ========================================
echo              Codex Mate Setup
echo ========================================
echo.
echo [1] Install Codex Mate
echo [2] Uninstall Codex Mate
echo [3] Update Codex Mate
echo [4] Exit
echo.
set /p choice=Please select an option [1-4]:

if "%choice%"=="1" goto install
if "%choice%"=="2" goto uninstall
if "%choice%"=="3" goto update
if "%choice%"=="4" goto end

echo.
echo Invalid choice.
pause
goto menu

:install
echo.
echo Installing Python package...
python -m pip install -e .
if errorlevel 1 goto error
echo.
echo Installing Codex Mate shortcut, uninstall entry, and transparent watcher...
python -m codex_session_delete setup
if errorlevel 1 goto error
echo.
echo Codex Mate installed successfully.
echo You can keep launching Codex from your normal entry point; Codex Mate will take over automatically.
pause
goto end

:uninstall
echo.
echo Uninstalling Codex Mate shortcut, uninstall entry, and transparent watcher...
python -m codex_session_delete remove
if errorlevel 1 goto error
echo.
echo Codex Mate uninstalled successfully.
pause
goto end

:update
echo.
echo Updating Codex Mate from GitHub Release...
python -m codex_session_delete update
if errorlevel 1 goto error
echo.
echo Codex Mate update finished.
pause
goto end

:error
echo.
echo Operation failed. Please check the error output above.
pause
exit /b 1

:end
endlocal
