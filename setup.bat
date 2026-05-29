@echo off
cd /d "%~dp0"
echo ============================================
echo Click'n'Load Bridge - Setup
echo ============================================
echo.
echo Python wird uberpruft...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [FEHLER] Python ist nicht installiert oder nicht im PATH.
    echo Bitte installiere Python von https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python gefunden
python --version
echo.
echo Erstelle virtuelles Environment...
python -m venv venv
if %errorlevel% neq 0 (
    echo [FEHLER] venv konnte nicht erstellt werden.
    pause
    exit /b 1
)
echo [OK] venv erstellt
echo.
echo Aktualisiere pip...
call venv\Scripts\python.exe -m pip install --upgrade pip
echo.
echo Installiere Abhangigkeiten...
call venv\Scripts\pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [FEHLER] pip install fehlgeschlagen.
    pause
    exit /b 1
)
echo [OK] Abhangigkeiten installiert
echo.
echo ============================================
echo Setup abgeschlossen!
echo.
echo Starten: pythonw main.py
echo Oder:    venv\Scripts\pythonw.exe main.py
echo.
echo Autostart einrichten: install_autostart.ps1 (als Admin)
echo ============================================
pause
