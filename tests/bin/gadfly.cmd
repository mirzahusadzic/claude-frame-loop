@echo off
where py >nul 2>nul
if errorlevel 1 (
  python "%~dp0gadfly" %*
) else (
  py -3 "%~dp0gadfly" %*
)
