@echo off
cd /d "%~dp0"
echo ============================================
echo Baue ClickNLoadBridge.exe ...
echo ============================================
echo.

pyinstaller --onefile --windowed ^
    --uac-admin ^
    --name "ClickNLoadBridge" ^
    --version-file version_info.txt ^
    --icon icon.ico ^
    --hidden-import myjd ^
    --hidden-import main ^
    --hidden-import dlc ^
    --hidden-import pythoncom ^
    --hidden-import win32com.client ^
    --hidden-import win32com ^
    --collect-all pywin32 ^
    run.py

if %errorlevel% equ 0 (
    echo.
    echo [OK] Build erfolgreich!
    echo EXE: dist\ClickNLoadBridge.exe
    echo.
    echo Die EXE kann jetzt ausgefuhrt werden.
) else (
    echo.
    echo [FEHLER] Build fehlgeschlagen
    echo Details siehe oben.
)
pause
