@echo off

REM 1. Активация окружения (Папка venv находится прямо здесь)
REM Имя папки исправлено на venv (без точки)
call venv\Scripts\activate.bat

REM 2. Запуск PostgreSQL (docker-compose.yml находится прямо здесь)
docker compose up -d 

REM 3. Запуск бота
python RPBot3.0.py

echo.
echo ---- Бот завершил работу или произошла ошибка ----
pause