@echo off
cd /d "%~dp0"

echo 🧠 Startējam datu kolekciju un AI treniņu...

:: 1. Savāc tirgus datus
start cmd /k python collect_all_data.py
timeout /t 3 >nul

:: 2. Apzīmē (label) kandidātus pēc 6h (pārbauda cenu izmaiņas)
start cmd /k python label_candidates.py
timeout /t 3 >nul

:: 3. Trenē individuālos AI modeļus no pending_training.json
start cmd /k python train_pending_models.py
timeout /t 3 >nul

:: 4. Trenē globālo AI modeli no labeled_candidates.csv
start cmd /k python train_from_labeled.py
timeout /t 3 >nul

pause

