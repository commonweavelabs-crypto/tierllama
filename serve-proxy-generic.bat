@echo off
rem Tierllama proxy :8846
cd /d %~dp0
python -m uvicorn tierllama.proxy:app --host 127.0.0.1 --port 8846
