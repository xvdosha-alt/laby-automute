@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist "dist" mkdir dist

echo [build] chatcopy...
call gradlew.bat createReleaseJar --no-daemon
if errorlevel 1 (
  echo [build] gradle failed
  exit /b 1
)

if not exist "build\libs\chatcopy-release.jar" (
  echo [build] jar not found
  exit /b 1
)

copy /y "build\libs\chatcopy-release.jar" "dist\chatcopy.jar" >nul
echo [build] done: dist\chatcopy.jar
dir "dist\chatcopy.jar"
exit /b 0
