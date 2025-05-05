@echo off
setlocal EnableDelayedExpansion

echo 🛑 Meklējam *telegram_loop.py* procesus...

REM Ciklam cauri visiem python.exe procesiem
for /f "skip=3 tokens=2,3,*" %%A in ('tasklist /v /fi "imagename eq python.exe"') do (
    echo %%C | findstr /i "telegram_loop.py" >nul
    if !errorlevel! == 0 (
        echo 🚫 Atrasts PID: %%A — komanda: %%C
        taskkill /PID %%A /F >nul 2>&1
    )
)

echo ⏳ Gaidām, kamēr procesi izbeidzas...
timeout /t 2 /nobreak >nul

echo 🧹 Dzēšam telegram_default.lock failu, ja tāds eksistē...
if exist telegram_default.lock (
    attrib -r -s -h telegram_default.lock >nul 2>&1
    del /f /q telegram_default.lock >nul 2>&1
    if exist telegram_default.lock (
        echo ⚠️ Neizdevās izdzēst telegram_default.lock!
    ) else (
        echo ✅ telegram_default.lock veiksmīgi dzēsts.
    )
) else (
    echo ℹ️ Fails telegram_default.lock nav atrasts.
)

REM Pārbaude: vai vēl kāds palicis?
echo 🔍 Pārbaude — vai vēl ir dzīvi telegram_loop.py procesi:
set FOUND=0
for /f "skip=3 tokens=2,3,*" %%A in ('tasklist /v /fi "imagename eq python.exe"') do (
    echo %%C | findstr /i "telegram_loop.py" >nul
    if !errorlevel! == 0 (
        echo ⚠️ Joprojām darbojas: PID %%A — %%C
        set FOUND=1
    )
)

if "!FOUND!"=="0" (
    echo ✅ Telegram loop veiksmīgi apturēts.
) else (
    echo ⚠️ Kāds process joprojām aktīvs. Iespējams, to startē automātiski!
)

pause
