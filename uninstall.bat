@echo off
setlocal EnableDelayedExpansion

:: Silent mode for re-installs
set "SILENT=0"
if /I "%~1"=="silent" set "SILENT=1"

:: Derive install directory from this script's location
set "INSTALL_DIR=%~dp0"

:: The uninstaller must live inside the install directory.
if not exist "%INSTALL_DIR%\WhyType.bat" (
    if %SILENT%==0 (
        echo ERROR: This uninstaller must be run from the WhyType installation directory.
        pause
    )
    exit /b 1
)

if %SILENT%==0 (
    echo ========================================
    echo       Why Type - Uninstaller
echo ========================================
    echo.
    echo This will remove Why Type from:
    echo   %INSTALL_DIR%
    echo.
    set /p CONFIRM="Are you sure? [Y/N]: "
    if /I not "!CONFIRM!"=="Y" (
        echo Uninstall cancelled.
        pause
        exit /b 0
    )
    echo.
)

:: Remove shortcuts from all possible locations
if %SILENT%==0 echo Removing shortcuts...
del "%USERPROFILE%\Desktop\Why Type.lnk" >nul 2>&1
del "%PUBLIC%\Desktop\Why Type.lnk" >nul 2>&1
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Why Type.lnk" >nul 2>&1
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Why Type Settings.lnk" >nul 2>&1
del "%ProgramData%\Microsoft\Windows\Start Menu\Programs\Why Type.lnk" >nul 2>&1
del "%ProgramData%\Microsoft\Windows\Start Menu\Programs\Why Type Settings.lnk" >nul 2>&1

:: Remove registry entries from both hives
if %SILENT%==0 echo Removing registry entries...
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\WhyType" /f >nul 2>&1
reg delete "HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\WhyType" /f >nul 2>&1

:: Delete application files (skip this uninstaller while it's running)
if %SILENT%==0 echo Removing application files...
for %%F in ("%INSTALL_DIR%\*") do (
    if /I not "%%~nxF"=="uninstall.bat" del /F /Q "%%F" >nul 2>&1
)
for /D %%D in ("%INSTALL_DIR%\*") do rmdir /S /Q "%%D" >nul 2>&1

:: Try to remove the directory itself. This may fail because
:: this batch file is still running from inside it.
rmdir /S /Q "%INSTALL_DIR%" >nul 2>&1

:: If the directory still exists, move it to temp for cleanup
if exist "%INSTALL_DIR%" (
    if %SILENT%==0 echo Scheduling remaining files for cleanup...
    move /Y "%INSTALL_DIR%" "%TEMP%\WhyType_Old_%RANDOM%" >nul 2>&1
)

if %SILENT%==0 (
    echo.
    echo ========================================
    echo Uninstall complete.
    echo.
    echo Note: Your settings and downloaded models
    echo were preserved in %%LOCALAPPDATA%%\WhyType
echo ========================================
    pause
)
