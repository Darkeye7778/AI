@echo off
cd /d "%~dp0"
echo Starting Personal Assistant...
echo.
if exist "dist\PersonalAssistant.exe" (
    dist\PersonalAssistant.exe
) else (
    echo ERROR: dist\PersonalAssistant.exe not found. Run build_exe.bat first.
)
echo.
echo Exit code: %ERRORLEVEL%
if %ERRORLEVEL% neq 0 (
    echo Check data\crash.log for details.
)
pause