@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "PYTHON_EXE="
for %%P in ("%~dp0.venv\Scripts\python.exe" "%USERPROFILE%\Desktop\Arte\.venv\Scripts\python.exe" "%USERPROFILE%\.venv\Scripts\python.exe" "%~dp0..\.venv\Scripts\python.exe" "%~dp0..\..\.venv\Scripts\python.exe") do (
  if not defined PYTHON_EXE if exist "%%~fP" set "PYTHON_EXE="%%~fP""
)
if not defined PYTHON_EXE (
  where py >nul 2>nul && set "PYTHON_EXE=py -3"
)
if not defined PYTHON_EXE (
  where python >nul 2>nul && set "PYTHON_EXE=python"
)
if not defined PYTHON_EXE (
  echo Python nao encontrado. Execute primeiro INSTALAR.bat
  pause
  exit /b 1
)
echo A iniciar Caca a Arte Scout em http://127.0.0.1:8766 ...
%PYTHON_EXE% "%~dp0Caca_Arte_Scout.py"
if errorlevel 1 pause
endlocal
