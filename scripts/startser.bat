@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ADDONS=C:\.minecraft\labymod-neo\addons"
set "MOD_A=screenshotbridge.jar"
set "MOD_B=autologin.jar"
set "MOD_C=chatcopy.jar"

if exist "%MOD_A%" if exist "%MOD_B%" if exist "%MOD_C%" (
  call :sync_mods
) else (
  echo [startser] addon jars missing, skip sync
)

echo [startser] stopping previous bot instances...
set "MAIN_SCRIPT=%~dp0main.py"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$main = (Resolve-Path -LiteralPath '%MAIN_SCRIPT%').Path.ToLower();" ^
  "Get-CimInstance Win32_Process | Where-Object { ($_.Name -eq 'python.exe' -or $_.Name -eq 'pythonw.exe') -and $_.CommandLine } | ForEach-Object { $cmd = $_.CommandLine.ToLower(); if ($cmd.Contains($main)) { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } }"
timeout /t 1 /nobreak >nul

echo [startser] installing dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo [startser] pip failed
  pause
  exit /b 1
)

where pythonw >nul 2>&1
if errorlevel 1 (
  set "PY=python"
) else (
  set "PY=pythonw"
)

echo [startser] starting moderator (%PY%)...
start "" "%PY%" "%~dp0main.py"
timeout /t 2 /nobreak >nul
start "" http://127.0.0.1:9999
echo [startser] moderator dashboard: http://127.0.0.1:9999
echo [startser] moderation is OFF by default — press Start in Clients tab
exit /b 0

:sync_mods
if not exist "%ADDONS%" (
  echo [startser] creating %ADDONS%
  mkdir "%ADDONS%" 2>nul
)
call :sync_one "%MOD_A%" screenshotbridge
call :sync_one "%MOD_B%" autologin
call :sync_one "%MOD_C%" chatcopy
call :remove_prefix proxybridge
call :remove_prefix fullbridge
echo [startser] removed proxybridge/fullbridge from addons
goto :eof

:sync_one
set "JAR=%~1"
set "PREFIX=%~2"
set "SRC=%~dp0%JAR%"
set "DST=%ADDONS%\%JAR%"

if not exist "%SRC%" (
  echo [startser] missing %JAR%, skip
  goto :eof
)

if not exist "%DST%" goto sync_one_install

fc /b "%SRC%" "%DST%" >nul 2>&1
if errorlevel 1 goto sync_one_update
echo [startser] %JAR% ok
goto :eof

:sync_one_install
echo [startser] install %JAR%
call :remove_prefix "%PREFIX%"
copy /y "%SRC%" "%DST%" >nul
goto :eof

:sync_one_update
echo [startser] update %JAR%
call :remove_prefix "%PREFIX%"
copy /y "%SRC%" "%DST%" >nul
goto :eof

:remove_prefix
set "PFX=%~1"
for %%F in ("%ADDONS%\%PFX%*.jar") do del /f /q "%%F" 2>nul
goto :eof
