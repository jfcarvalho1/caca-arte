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
echo.
echo TESTE REAL DAS FONTES (Arte, Livros e Usados)
echo Demora cerca de 5 a 10 minutos. Nao feche esta janela.
echo No fim abre-se a pasta com o ZIP para enviar ao Claude.
echo.
%PYTHON_EXE% "%~dp0diagnostico_fontes.py" --area todas
endlocal
