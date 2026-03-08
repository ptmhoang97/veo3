@echo off
REM === Run Firefox with project profile ===
REM Doc profile name tu config.ini

setlocal enabledelayedexpansion

REM Tim profile name tu config.ini
set "PROFILE_NAME="
for /f "tokens=1,* delims==" %%a in ('findstr /i "profile_path" "%~dp0source\config.ini"') do (
    set "PROFILE_NAME=%%b"
)

REM Trim spaces
set "PROFILE_NAME=%PROFILE_NAME: =%"

if "%PROFILE_NAME%"=="" (
    echo ERROR: Khong tim thay profile_path trong config.ini
    pause
    exit /b 1
)

set "PROFILE_DIR=%~dp0tools\profiles\%PROFILE_NAME%"

echo ============================================
echo  Firefox Profile Launcher
echo ============================================
echo  Profile: %PROFILE_NAME%
echo  Path:    %PROFILE_DIR%
echo ============================================

if not exist "%PROFILE_DIR%" (
    echo ERROR: Profile folder khong ton tai: %PROFILE_DIR%
    pause
    exit /b 1
)

echo.
echo Dang mo Firefox voi profile "%PROFILE_NAME%"...
echo Hay dang nhap Google/Gemini roi dong Firefox lai.
echo.

start "" "C:\Program Files\Mozilla Firefox\firefox.exe" -profile "%PROFILE_DIR%"
