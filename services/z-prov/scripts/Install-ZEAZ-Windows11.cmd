@echo off
setlocal enabledelayedexpansion

title ZEAZ Provider Windows 11 Installer

:: Check for PowerShell 7 or Windows PowerShell
where pwsh.exe >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "PS_CMD=pwsh.exe"
) else (
    set "PS_CMD=powershell.exe"
)

echo ===================================================
echo     ZEAZ Provider Automated Installer (Windows 11)
echo ===================================================
echo.

%PS_CMD% -ExecutionPolicy Bypass -NoProfile -File "%~dp0Install-ZEAZ-Windows11.ps1" -Apply %*

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Installation failed. Press any key to exit.
    pause >nul
    exit /b %ERRORLEVEL%
)

echo.
echo [SUCCESS] Installation finished successfully.
echo.
pause
endlocal
