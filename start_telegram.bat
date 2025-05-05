@echo off
chcp 65001
title 🤖 Telegram Bots — MEXC Projekts
cd /d "%~dp0"

echo 📡 Startējam Telegram komandu klausītāju...
python telegram_loop.py

pause
