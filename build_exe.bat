@echo off
cd /d "%~dp0"

if exist "venv\Scripts\python.exe" (
    set PY=venv\Scripts\python.exe
) else (
    set PY=python
)

echo [1/3] Installing all app dependencies into venv...
"%PY%" -m pip install -r requirements-platform.txt
"%PY%" -m pip install -r requirements.txt
"%PY%" -m pip install pyinstaller llama-cpp-python

echo.
echo [2/3] Verifying critical imports...
"%PY%" -c "import sqlalchemy; import assistant.db.database; print('Dependencies OK')"
if errorlevel 1 (
    echo DEPENDENCY CHECK FAILED
    pause
    exit /b 1
)

echo.
echo [3/3] Building executable (this takes several minutes)...
"%PY%" -m PyInstaller build_exe.spec --noconfirm --distpath "%~dp0dist" --workpath "%~dp0build"
if errorlevel 1 (
    echo.
    echo BUILD FAILED — see errors above.
    pause
    exit /b 1
)

echo.
echo Done!
echo   %~dp0dist\PersonalAssistant.exe
echo.
echo Keep the exe inside D:\AI_Assistant so it can find models\ and data\
pause