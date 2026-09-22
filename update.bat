@echo off
rem Tierllama updater: git pull + restart services
echo Updating Tierllama...
git -C "%~dp0." pull
if errorlevel 1 (
    echo ERROR: git pull failed. Check your connection.
    pause
    exit /b 1
)
taskkill /F /FI "WINDOWTITLE eq tierllama-proxy*" >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8846 ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8848 ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1
timeout /t 2 >nul
start "tierllama-proxy" /min cmd /c "%~dp0serve-proxy.bat"
start "tierllama-dashboard" /min cmd /c "%~dp0serve-dashboard.bat"
echo.
echo Updated and restarted. Dashboard: http://127.0.0.1:8848
pause
