@echo off
rem Tierllama installer (J9): zero-to-working on Windows
echo ============================================
echo   Tierllama installer
echo ============================================
echo.
echo [1/5] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo   ERROR: Python not found. Install Python 3.11+ from python.org
    echo   then re-run this installer.
    pause
    exit /b 1
)
echo   Python OK.
echo.
echo [2/5] Installing Python dependencies...
python -m pip install -q fastapi uvicorn pydantic 2>nul
if errorlevel 1 (
    echo   ERROR: pip install failed. Check your internet connection.
    pause
    exit /b 1
)
echo   Dependencies OK.
echo.
echo [3/5] Checking Ollama...
curl -s http://127.0.0.1:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo   WARNING: Ollama is not running or not installed.
    echo   Tierllama needs Ollama to route locally.
    echo   Download from https://ollama.com then run: ollama pull qwen3:4b
    echo   (Continuing install - you can set up Ollama later.)
) else (
    echo   Ollama OK.
)
echo.
echo [4/5] Setting up auto-start (dashboard + proxy at logon)...
copy /Y "%~dp0serve-proxy.bat" "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\serve-tierllama-proxy.bat" >nul 2>&1
copy /Y "%~dp0serve-dashboard.bat" "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\serve-tierllama-dashboard.bat" >nul 2>&1
echo   Auto-start OK.
echo.
echo [5/5] Starting Tierllama...
start "tierllama-proxy" /min cmd /c "%~dp0serve-proxy.bat"
timeout /t 3 >nul
start "" http://127.0.0.1:8848
echo.
echo ============================================
echo   Tierllama is installed!
echo   Dashboard:  http://127.0.0.1:8848
echo   Router:     http://127.0.0.1:8846/v1
echo   Chrome tip: click Install in the address bar to get
echo   a desktop icon + taskbar entry for the dashboard.
echo ============================================
pause
