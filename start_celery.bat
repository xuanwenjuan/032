@echo off
cd /d %~dp0backend
celery -A app.workers.celery_app worker --loglevel=info --pool=solo
