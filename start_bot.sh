#!/usr/bin/env bash
# start_bot.sh — должен лежать в /root/RPBOT-MAIN

# 1) Переходим в каталог с ботом
cd "/root/RPBOT-MAIN/Python files"

source ../.venv/bin/activate 

# 3) Запускаем бота (замена exec — чтобы система получала статус процесса бота)
exec python RPBot3.0.py