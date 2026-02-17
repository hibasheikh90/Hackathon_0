@echo off
REM ============================================================
REM  AI Employee Scheduler -- Windows Task Scheduler Setup
REM  Run this script as Administrator
REM ============================================================

echo.
echo  AI Employee -- Task Scheduler Setup
echo  ====================================
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

REM --- Validate script exists ---
if not exist "%PROJECT_DIR%\scripts\run_ai_employee.py" (
    echo  [ERROR] run_ai_employee.py not found at:
    echo          %PROJECT_DIR%\scripts\run_ai_employee.py
    pause
    exit /b 1
)

REM --- Delete existing task if present ---
schtasks /query /tn "AI Employee Scheduler" >nul 2>&1
if %errorlevel% equ 0 (
    echo  Removing existing task...
    schtasks /delete /tn "AI Employee Scheduler" /f >nul 2>&1
)

REM --- Create the scheduled task ---
echo  Creating scheduled task (every 5 minutes)...
echo.

schtasks /create ^
  /tn "AI Employee Scheduler" ^
  /tr "\"%PYTHON_PATH%\" \"%PROJECT_DIR%\scripts\run_ai_employee.py\" --once" ^
  /sc minute ^
  /mo 5 ^
  /rl HIGHEST ^
  /f

if %errorlevel% equ 0 (
    echo.
    echo  [OK] Task "AI Employee Scheduler" created successfully.
    echo.
    echo  The scheduler will run every 5 minutes.
    echo  Log file: %PROJECT_DIR%\scripts\scheduler.log
    echo.
    echo  Commands:
    echo    Run now:    schtasks /run /tn "AI Employee Scheduler"
    echo    Check:      schtasks /query /tn "AI Employee Scheduler" /fo LIST
    echo    Remove:     schtasks /delete /tn "AI Employee Scheduler" /f
) else (
    echo.
    echo  [ERROR] Failed to create task. Are you running as Administrator?
)

echo.
pause
