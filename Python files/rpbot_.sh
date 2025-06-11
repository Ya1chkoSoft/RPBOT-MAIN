#!/bin/bash

# Переход в директорию с ботом
cd "/RPBOT3/RRBOT/RP BOT 3.5/RPBOT/Python files"
source ../../.venv/bin/activate

# Запуск бота с логированием
echo "Запуск бота..." > logs/last_run.log
python RPBot3.0.py >> logs/last_run.log 2>&1

# Вывод в консоль после завершения
echo ""
echo "---- Бот завершил работу или произошла ошибка ----"