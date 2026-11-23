@echo off
where py >nul 2>nul
if errorlevel 1 (
  python "%~dp0claude" %*
) else (
  py -3 "%~dp0claude" %*
)
