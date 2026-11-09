@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set "PY="
for %%C in ("py -3" "python" "python3") do (
  if not defined PY (
    %%~C -c "import sys; sys.exit(0 if sys.version_info[:2] >= (3, 11) else 1)" >nul 2>nul && set "PY=%%~C"
  )
)
if not defined PY goto nopython
%PY% hope.py %*
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" if "%~1"=="" pause
exit /b %CODE%

:nopython
echo.
echo Python 3.11 or newer is required but was not found.
echo Install it from https://www.python.org/downloads/
echo and tick "Add python.exe to PATH" in the installer, then run this file again.
echo.
pause
exit /b 1
