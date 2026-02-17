@echo off
REM ============================================================
REM  Gold Tier AI Employee — Windows Task Scheduler Setup
REM  Run this script as Administrator
REM ============================================================

echo.
echo  Gold Tier AI Employee -- Task Scheduler Setup
echo  ===============================================
echo.

REM --- Detect project path ---
set "PROJECT_DIR=%~dp0.."
pushd "%PROJECT_DIR%"
set "PROJECT_DIR=%CD%"
popd

echo  Project path: %PROJECT_DIR%
echo.

REM --- Detect Python ---
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] Python not found in PATH.
    echo          Install Python or add it to your system PATH.
    pause
    exit /b 1
)

for /f "delims=" %%i in ('where python') do set "PYTHON_PATH=%%i"
echo  Python path:  %PYTHON_PATH%
echo.

REM --- Validate Gold scheduler exists ---
if not exist "%PROJECT_DIR%\core\scheduler.py" (
    echo  [ERROR] core\scheduler.py not found.
    echo          Run this from the Bronze project root.
    pause
    exit /b 1
)

REM --- Validate config ---
echo  Running config validation...
"%PYTHON_PATH%" -m core.validator
if %errorlevel% neq 0 (
    echo.
    echo  [WARN] Some checks failed. The scheduler may not work fully.
    echo         Fix the issues above, or continue anyway.
    echo.
    choice /C YN /M "Continue with setup?"
    if errorlevel 2 exit /b 1
)

echo.

REM --- Delete existing task if present ---
schtasks /query /tn "AI Employee Gold Scheduler" >nul 2>&1
if %errorlevel% equ 0 (
    echo  Removing existing Gold scheduler task...
    schtasks /delete /tn "AI Employee Gold Scheduler" /f >nul 2>&1
)

REM --- Also remove old Silver task if present ---
schtasks /query /tn "AI Employee Scheduler" >nul 2>&1
if %errorlevel% equ 0 (
    echo  Removing old Silver scheduler task...
    schtasks /delete /tn "AI Employee Scheduler" /f >nul 2>&1
)

REM --- Create the Gold scheduler task ---
echo  Creating Gold Tier scheduled task (every 5 minutes)...
echo.

schtasks /create ^
  /tn "AI Employee Gold Scheduler" ^
  /tr "\"%PYTHON_PATH%\" -m core.scheduler --once" ^
  /sc minute ^
  /mo 5 ^
  /rl HIGHEST ^
  /sd %date% ^
  /f

if %errorlevel% equ 0 (
    echo.
    echo  [OK] Task "AI Employee Gold Scheduler" created successfully.
    echo.
    echo  The Gold scheduler will run every 5 minutes and execute:
    echo    - Gmail inbox check
    echo    - Vault scan (triage + plan)
    echo    - Social content queue processing
    echo    - Odoo sync
    echo    - Log rotation
    echo    - Daily report (at 18:00)
    echo    - Weekly CEO briefing (Monday 08:00)
    echo.
    echo  Log files:
    echo    Scheduler: %PROJECT_DIR%\logs\scheduler.log
    echo    Errors:    %PROJECT_DIR%\logs\error.log
    echo    Audit:     %PROJECT_DIR%\logs\audit.log
    echo.
    echo  Commands:
    echo    Run now:    schtasks /run /tn "AI Employee Gold Scheduler"
    echo    Check:      schtasks /query /tn "AI Employee Gold Scheduler" /fo LIST
    echo    Remove:     schtasks /delete /tn "AI Employee Gold Scheduler" /f
) else (
    echo.
    echo  [ERROR] Failed to create task. Are you running as Administrator?
)

echo.
pause
