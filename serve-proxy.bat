@echo off
rem Tierllama proxy (dogfood) - OpenAI-compatible endpoint :8846
cd /d C:\Users\Guilherme\tierllama
C:\Python313\python.exe -m uvicorn tierllama.proxy:app --host 127.0.0.1 --port 8846
