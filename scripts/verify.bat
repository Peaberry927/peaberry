@echo off
setlocal EnableExtensions

set "PYTHON_CMD="

where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 -c "import sys" >nul 2>nul
  if %ERRORLEVEL%==0 set "PYTHON_CMD=py -3"
)

if not defined PYTHON_CMD (
  where python >nul 2>nul
  if %ERRORLEVEL%==0 set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
  where python3 >nul 2>nul
  if %ERRORLEVEL%==0 set "PYTHON_CMD=python3"
)

if not defined PYTHON_CMD (
  echo No Python launcher found. Tried: py -3, python, python3.
  exit /b 1
)

echo Using %PYTHON_CMD%
set "PYTHONPATH=src"
%PYTHON_CMD% -m unittest discover -s tests
if errorlevel 1 exit /b 1
%PYTHON_CMD% -m compileall src tests
if errorlevel 1 exit /b 1

endlocal
