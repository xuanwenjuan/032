@echo off
cd /d %~dp0backend
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
