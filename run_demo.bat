@echo off
cd /d "%~dp0"
title AdaptShield v2.0 Launcher

if exist "config.env" (
    for /f "usebackq tokens=1,* delims==" %%a in ("config.env") do (
        if "%%a"=="GROQ_API_KEY" set "GROQ_API_KEY=%%b"
    )
)

echo ========================================================
echo   AdaptShield v2.0 - AI Prompt ^& Document Security
echo ========================================================
echo.
echo [1] Launch Native Desktop Mode (pywebview)
echo [2] Launch Local Web Server (http://127.0.0.1:8000)
echo [3] Run Model Evaluation Benchmark
echo.
set /p mode="Select launch mode [1-3, default 1]: "

if "%mode%"=="2" (
    echo Starting AdaptShield Web Server...
    python server.py
) else if "%mode%"=="3" (
    echo Running empirical evaluation on held-out test split...
    python evaluate_models.py
    pause
) else (
    echo Starting AdaptShield in Native Desktop Window...
    python desktop_app.py
)
