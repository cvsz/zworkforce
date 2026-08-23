@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-ZARVIS-OwnerDomain.ps1" -ServerHost "192.168.74.130" -SshUser "cvsz" -SshPort 22
echo.
pause
