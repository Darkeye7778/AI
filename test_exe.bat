@echo off
cd /d "%~dp0"
echo Running exe smoke test...
dist\PersonalAssistant.exe smoke
echo.
echo Smoke test exit code: %ERRORLEVEL%
pause