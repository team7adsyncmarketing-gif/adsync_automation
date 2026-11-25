@echo off
setlocal
if defined FACELESS_HOME (
  set "FH=%FACELESS_HOME%"
) else (
  set "FH=%USERPROFILE%\.faceless-shorts"
)

if exist "%FH%\venv\Scripts\python.exe" (
  "%FH%\venv\Scripts\python.exe" %*
  exit /b %ERRORLEVEL%
)

where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
  python %*
  exit /b %ERRORLEVEL%
)

where py >nul 2>nul
if %ERRORLEVEL% equ 0 (
  py -3 %*
  exit /b %ERRORLEVEL%
)

echo [ERROR] Python not found. Run scripts\setup.py first. 1>&2
exit /b 1

