@echo off
rem Tierllama dashboard :8848
cd /d %~dp0
python -m uvicorn tierllama.webapp:app --host 127.0.0.1 --port 8848
