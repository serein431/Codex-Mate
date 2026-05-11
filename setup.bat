@echo off
setlocal
cd /d "%~dp0"
set "CODEX_MATE_EXE=%~dp0CodexMate.exe"
set "CODEX_MATE_PY=python -m codex_mate"

:menu
cls
echo ========================================
echo              Codex Mate Setup
echo ========================================
echo.
echo [1] Install Codex Mate
echo [2] Uninstall Codex Mate
echo [3] Update Codex Mate
echo [4] Export diagnostic logs
echo [5] Exit
echo.
set /p choice=Please select an option [1-5]:

if "%choice%"=="1" goto install
if "%choice%"=="2" goto uninstall
if "%choice%"=="3" goto update
if "%choice%"=="4" goto logs
if "%choice%"=="5" goto end

echo.
echo Invalid choice.
pause
goto menu

:install
echo.
if exist "%CODEX_MATE_EXE%" goto install_binary
where python >nul 2>nul
if errorlevel 1 goto missing_python
echo Installing Python package...
python -m pip install -e .
if errorlevel 1 goto error
echo.
echo Installing Codex Mate shortcut, uninstall entry, and transparent watcher...
%CODEX_MATE_PY% setup
if errorlevel 1 goto error
goto install_done

:install_binary
echo Using bundled CodexMate.exe.
echo.
echo Installing Codex Mate shortcut, uninstall entry, and transparent watcher...
"%CODEX_MATE_EXE%" setup
if errorlevel 1 goto error

:install_done
echo.
echo Codex Mate installed successfully.
echo You can keep launching Codex from your normal entry point; Codex Mate will take over automatically.
pause
goto end

:uninstall
echo.
echo Uninstalling Codex Mate shortcut, uninstall entry, and transparent watcher...
if exist "%CODEX_MATE_EXE%" (
    "%CODEX_MATE_EXE%" remove
) else (
    %CODEX_MATE_PY% remove
)
if errorlevel 1 goto error
echo.
echo Codex Mate uninstalled successfully.
pause
goto end

:update
echo.
echo Updating Codex Mate from GitHub Release...
if exist "%CODEX_MATE_EXE%" (
    echo Bundled executable installs are updated by downloading the latest CodexMate-windows.zip and running setup.bat again.
) else (
    %CODEX_MATE_PY% update
)
if errorlevel 1 goto error
echo.
echo Codex Mate update finished.
pause
goto end

:logs
echo.
echo Exporting diagnostic logs...
if exist "%CODEX_MATE_EXE%" (
    "%CODEX_MATE_EXE%" logs
) else (
    %CODEX_MATE_PY% logs
)
if errorlevel 1 goto error
echo.
echo Please send the generated CodexMate-diagnostics zip file to the maintainer.
pause
goto end

:error
echo.
echo Operation failed. Please check the error output above.
pause
exit /b 1

:missing_python
echo.
echo Python was not found and CodexMate.exe is not in this folder.
echo Download CodexMate-windows.zip from the latest GitHub Release, unzip it, then run setup.bat again.
pause
exit /b 1

:end
endlocal
