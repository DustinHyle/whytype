@echo off
setlocal EnableDelayedExpansion

echo ========================================
echo        Why Type - Installer
echo ========================================
echo.

:: --- Determine source directory (where this script lives) ---
set "SOURCE_DIR=%~dp0"

:: --- Detect admin privileges ---
net session >nul 2>&1
if %errorLevel% == 0 goto :admin_yes
set "ADMIN=0"
set "INSTALL_DIR=%LOCALAPPDATA%\Programs\WhyType"
set "REG_ROOT=HKCU"
set "START_MENU=%APPDATA%\Microsoft\Windows\Start Menu\Programs"
set "DESKTOP_DIR=%USERPROFILE%\Desktop"
echo Installing for current user...
goto :admin_done
:admin_yes
set "ADMIN=1"
set "INSTALL_DIR=%ProgramFiles%\WhyType"
set "REG_ROOT=HKLM"
set "START_MENU=%ProgramData%\Microsoft\Windows\Start Menu\Programs"
set "DESKTOP_DIR=%PUBLIC%\Desktop"
echo Installing system-wide (requires admin)...
:admin_done
echo Install directory: %INSTALL_DIR%
echo.

:: --- Check for existing installation ---
if not exist "%INSTALL_DIR%\WhyType.bat" if not exist "%INSTALL_DIR%\.venv" goto :no_previous
echo Why Type is already installed at %INSTALL_DIR%.
set /p OVERWRITE="Overwrite? [Y/N]: "
if /I "%OVERWRITE%"=="Y" goto :do_overwrite
echo Installation cancelled.
pause
exit /b 0
:do_overwrite
echo Removing previous installation...
:: Kill any running app instances aggressively
taskkill /F /IM pythonw.exe >nul 2>&1
taskkill /F /T /IM pythonw.exe >nul 2>&1
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM WhyType.exe >nul 2>&1
powershell -ExecutionPolicy Bypass -Command "Get-Process | Where-Object {$_.ProcessName -match 'python|WhyType'} | Stop-Process -Force -ErrorAction SilentlyContinue" >nul 2>&1
timeout /t 3 /nobreak >nul
:: Check if any are still running
tasklist /FI "IMAGENAME eq pythonw.exe" 2>nul | findstr /I "pythonw" >nul
if not errorlevel 1 (
    echo.
    echo WARNING: WhyType is still running. Please open Task Manager,
    echo end any "pythonw" or "WhyType" processes, then press any key.
    pause
)
rmdir /S /Q "%INSTALL_DIR%" 2>nul
timeout /t 2 /nobreak >nul
:: If still locked, move to temp and clean up later
if exist "%INSTALL_DIR%" (
    echo Some files were locked. Moving old installation to temp...
    move /Y "%INSTALL_DIR%" "%TEMP%\WhyType_Old_%RANDOM%" >nul 2>&1
    timeout /t 2 /nobreak >nul
)
:no_previous

:: --- Create install directory ---
mkdir "%INSTALL_DIR%" 2>nul
if not exist "%INSTALL_DIR%" (
    echo ERROR: Failed to create install directory. Check permissions.
    pause
    exit /b 1
)

:: --- Copy application files ---
echo Copying application files...
if not exist "%SOURCE_DIR%\whytype" (
    echo ERROR: Source directory "%SOURCE_DIR%\whytype" not found.
    echo Make sure you run this installer from the extracted distribution folder.
    pause
    exit /b 1
)
xcopy /E /I /Y "%SOURCE_DIR%\whytype" "%INSTALL_DIR%\whytype\" >nul
if errorlevel 1 (
    echo ERROR: Failed to copy application files.
    rmdir /S /Q "%INSTALL_DIR%" 2>nul
    pause
    exit /b 1
)
copy /Y "%SOURCE_DIR%\pyproject.toml" "%INSTALL_DIR%\" >nul
copy /Y "%SOURCE_DIR%\requirements.txt" "%INSTALL_DIR%\" >nul 2>&1 || rem optional file missing
copy /Y "%SOURCE_DIR%\README.md" "%INSTALL_DIR%\" >nul 2>&1 || rem optional file missing

:: --- Verify the whisper.cpp engine binary is present ---
:: GPU acceleration on Windows uses the Vulkan loader (vulkan-1.dll), which
:: ships with your GPU drivers; no separate install is normally needed.
if not exist "%INSTALL_DIR%\whytype\bin\whisper-cli.exe" (
    echo.
    echo WARNING: transcription engine binary ^(whisper-cli.exe^) is missing from
    echo this package. Use the Windows download, which bundles it.
    echo.
)

:: --- Find Python ---
set "PYTHON_CMD="

python --version >nul 2>&1
if not errorlevel 1 goto :python_found

py --version >nul 2>&1
if not errorlevel 1 goto :python_found_py

:: Python not found - download and install
echo Python not found. Downloading and installing...
echo (This may take a minute)
powershell -NoProfile -ExecutionPolicy Bypass -Command "& {Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.0/python-3.12.0-amd64.exe' -OutFile '%TEMP%\python-installer.exe'}" >nul 2>&1

if not exist "%TEMP%\python-installer.exe" (
    echo Failed to download Python installer.
    echo Please install Python 3.8+ manually from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Installing Python (per-user, no admin required)...
"%TEMP%\python-installer.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_launcher=1
set "PY_EXIT=%errorlevel%"
del "%TEMP%\python-installer.exe"

:: 3010 = success, reboot required
if %PY_EXIT% == 0 goto :python_installed_ok
if %PY_EXIT% == 3010 goto :python_installed_ok
echo Python installation failed (exit code %PY_EXIT%).
pause
exit /b 1
:python_installed_ok

:: Refresh PATH for this session
set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%PATH%"

python --version >nul 2>&1
if not errorlevel 1 goto :python_found
echo Python was installed but is not available in this session.
echo Please restart your computer and run this installer again.
pause
exit /b 1

:python_found_py
set "PYTHON_CMD=py"
goto :python_done

:python_found
set "PYTHON_CMD=python"

:python_done
for /f "tokens=2" %%i in ('%PYTHON_CMD% --version 2^>^&1') do set PYVER=%%i
echo Found Python %PYVER%

:: Validate Python version (3.8+)
echo %PYVER% | findstr /B /R "3\.[8-9] 3\.[1-9][0-9]" >nul
if not errorlevel 1 goto :python_version_ok
echo ERROR: Python %PYVER% is not supported. Python 3.8 or newer is required.
pause
exit /b 1
:python_version_ok

:: --- Create virtual environment ---
:: Always kill any running app instances first — they may lock venv files
taskkill /F /IM pythonw.exe >nul 2>&1
taskkill /F /IM whytype.exe >nul 2>&1
timeout /t 2 /nobreak >nul

if exist "%INSTALL_DIR%\.venv\Scripts\python.exe" goto :venv_exists
if exist "%INSTALL_DIR%\.venv" (
    echo Cleaning up old virtual environment...
    rmdir /S /Q "%INSTALL_DIR%\.venv" 2>nul
    timeout /t 2 /nobreak >nul
    if exist "%INSTALL_DIR%\.venv" (
        echo Old venv still locked. Moving to temp...
        move /Y "%INSTALL_DIR%\.venv" "%TEMP%\WhyType_Venv_Old_%RANDOM%" >nul 2>&1
        timeout /t 1 /nobreak >nul
    )
)
echo Creating virtual environment...
%PYTHON_CMD% -m venv "%INSTALL_DIR%\.venv"
if errorlevel 1 (
    echo Failed to create virtual environment.
    pause
    exit /b 1
)
:venv_exists

:: --- Install dependencies ---
echo.
echo Installing dependencies. This is quick — transcription runs on a bundled
echo whisper.cpp binary, so there is no PyTorch to download.
echo.

"%INSTALL_DIR%\.venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
    echo Failed to upgrade pip.
    pause
    exit /b 1
)

"%INSTALL_DIR%\.venv\Scripts\python.exe" -m pip install --no-compile --no-cache-dir --force-reinstall "%INSTALL_DIR%"
if errorlevel 1 (
    echo Failed to install WhyType and its dependencies.
    pause
    exit /b 1
)

:: --- Ask for model ---
:ask_model
echo.
echo ========================================
echo No transcription model is installed yet.
echo.
echo 1) Tiny    - Fastest, basic accuracy      (~75 MB)
echo 2) Base    - Fast, good balance            (~142 MB)
echo 3) Small   - Moderate, better accents      (~466 MB)  [recommended]
echo 4) Medium  - Slow, high accuracy           (~1.5 GB)
echo 5) Large   - Slowest, maximum accuracy     (~3.1 GB)
echo 6) Skip    - Download later from Settings
echo ========================================
set /p MODEL_CHOICE="Choose a model to download [1-6, default 3]: "

:: Default to Small (the recommended balance) when the user just presses Enter.
if "%MODEL_CHOICE%"=="" set "MODEL_NAME=small" & goto :download
if "%MODEL_CHOICE%"=="1" set "MODEL_NAME=tiny" & goto :download
if "%MODEL_CHOICE%"=="2" set "MODEL_NAME=base" & goto :download
if "%MODEL_CHOICE%"=="3" set "MODEL_NAME=small" & goto :download
if "%MODEL_CHOICE%"=="4" set "MODEL_NAME=medium" & goto :download
if "%MODEL_CHOICE%"=="5" set "MODEL_NAME=large-v3" & goto :download
if "%MODEL_CHOICE%"=="6" goto :skip_model
echo Invalid choice. Please enter a number from 1 to 6.
goto :ask_model

:download
echo.
echo Downloading %MODEL_NAME% model...
echo (This may take a few minutes depending on your connection)
"%INSTALL_DIR%\.venv\Scripts\python.exe" -c "from whytype.models import download_model; download_model('%MODEL_NAME%')"
if errorlevel 1 (
    echo.
    echo ERROR: Model download failed. You can try again later from Settings.
    goto :create_launcher
)

:: Verify the model file actually exists and save to config
:: Use Python exit code to avoid batch quote-nesting issues
echo.
echo Verifying download and saving config...
"%INSTALL_DIR%\.venv\Scripts\python.exe" -c "import os, json, sys; from whytype.models import is_model_downloaded; from platformdirs import user_config_dir; ok=is_model_downloaded('%MODEL_NAME%'); config_dir=user_config_dir('WhyType'); os.makedirs(config_dir,exist_ok=True); p=os.path.join(config_dir,'settings.json'); data={'shortcut':'ctrl+win','recording_mode':'hold','device':'auto','model':'%MODEL_NAME%'}; json.dump(data, open(p, 'w', encoding='utf-8'), indent=2); print('Config file:', p); sys.exit(0 if ok else 1)"
if errorlevel 1 (
    echo WARNING: Model download appeared to succeed but the file was not found.
    echo You can try downloading again from Settings.
) else (
    echo Model downloaded successfully. Config saved.
)
goto :create_launcher

:skip_model
echo.
echo Skipping model download. You can download one later from Settings.
:: Still write default config so shortcut is set
echo.
echo Setting default configuration...
"%INSTALL_DIR%\.venv\Scripts\python.exe" -c "import json, os; from platformdirs import user_config_dir; d=user_config_dir('WhyType'); os.makedirs(d, exist_ok=True); p=os.path.join(d,'settings.json'); data={'shortcut':'ctrl+win','recording_mode':'hold','device':'auto'}; json.dump(data, open(p, 'w', encoding='utf-8'), indent=2); print('Config dir:', d); print('Config file:', p)"

:create_launcher
:: --- Create launchers ---
echo.
echo Creating launchers...

:: Batch files for command-line use (start async so console closes)
(
echo @echo off
echo start "" "%%~dp0.venv\Scripts\WhyType.exe" -m whytype
) > "%INSTALL_DIR%\WhyType.bat"

(
echo @echo off
echo start "" "%%~dp0.venv\Scripts\WhyType.exe" -m whytype --settings
) > "%INSTALL_DIR%\Settings.bat"

:: --- Copy pythonw.exe to WhyType.exe so Task Manager shows the right name ---
echo Creating app executable...
copy /Y "%INSTALL_DIR%\.venv\Scripts\pythonw.exe" "%INSTALL_DIR%\.venv\Scripts\WhyType.exe" >nul
if not exist "%INSTALL_DIR%\.venv\Scripts\WhyType.exe" (
    echo ERROR: Failed to create WhyType.exe.
    pause
    exit /b 1
)

:: --- Shortcuts (point directly to WhyType.exe - no console window) ---
echo Creating shortcuts...
set "EXE=%INSTALL_DIR%\.venv\Scripts\WhyType.exe"
set "ICON=%INSTALL_DIR%\whytype\assets\icon.ico"

powershell -NoProfile -ExecutionPolicy Bypass -Command "& {$ws = New-Object -ComObject WScript.Shell; $sc = $ws.CreateShortcut('%START_MENU%\Why Type.lnk'); $sc.TargetPath = '%EXE%'; $sc.Arguments = '-m whytype'; $sc.WorkingDirectory = '%INSTALL_DIR%'; $sc.Description = 'Why Type - Voice Dictation'; $sc.IconLocation = '%ICON%'; $sc.Save()}" >nul 2>&1

powershell -NoProfile -ExecutionPolicy Bypass -Command "& {$ws = New-Object -ComObject WScript.Shell; $sc = $ws.CreateShortcut('%START_MENU%\Why Type Settings.lnk'); $sc.TargetPath = '%EXE%'; $sc.Arguments = '-m whytype --settings'; $sc.WorkingDirectory = '%INSTALL_DIR%'; $sc.Description = 'Why Type - Settings'; $sc.IconLocation = '%ICON%'; $sc.Save()}" >nul 2>&1

powershell -NoProfile -ExecutionPolicy Bypass -Command "& {$ws = New-Object -ComObject WScript.Shell; $sc = $ws.CreateShortcut('%DESKTOP_DIR%\Why Type.lnk'); $sc.TargetPath = '%EXE%'; $sc.Arguments = '-m whytype'; $sc.WorkingDirectory = '%INSTALL_DIR%'; $sc.Description = 'Why Type - Voice Dictation'; $sc.IconLocation = '%ICON%'; $sc.Save()}" >nul 2>&1

:: --- Copy uninstaller ---
copy /Y "%SOURCE_DIR%\uninstall.bat" "%INSTALL_DIR%\uninstall.bat" >nul 2>&1

:: --- Registry: Add/Remove Programs ---
echo Registering installation...
reg add "%REG_ROOT%\Software\Microsoft\Windows\CurrentVersion\Uninstall\WhyType" /f >nul 2>&1
reg add "%REG_ROOT%\Software\Microsoft\Windows\CurrentVersion\Uninstall\WhyType" /v DisplayName /d "Why Type" /f >nul 2>&1
reg add "%REG_ROOT%\Software\Microsoft\Windows\CurrentVersion\Uninstall\WhyType" /v DisplayVersion /d "1.1.16" /f >nul 2>&1
reg add "%REG_ROOT%\Software\Microsoft\Windows\CurrentVersion\Uninstall\WhyType" /v Publisher /d "WhyType" /f >nul 2>&1
reg add "%REG_ROOT%\Software\Microsoft\Windows\CurrentVersion\Uninstall\WhyType" /v InstallLocation /d "%INSTALL_DIR%" /f >nul 2>&1
reg add "%REG_ROOT%\Software\Microsoft\Windows\CurrentVersion\Uninstall\WhyType" /v UninstallString /d "\"%INSTALL_DIR%\uninstall.bat\"" /f >nul 2>&1

echo.
echo ========================================
echo Installation complete!
echo.
echo Why Type is installed at:
echo   %INSTALL_DIR%
echo.
echo IMPORTANT NOTES:
echo  - Default shortcut: Ctrl+Win (change in Settings)
echo  - Runs silently in the system tray — no terminal window
echo  - Right-click the tray icon for menu options
echo  - Use Start Menu ^> Why Type Settings to open settings
echo.
echo Launch from your Start Menu or desktop.
echo ========================================
pause
