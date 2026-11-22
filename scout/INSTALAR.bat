@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo ==============================================
echo  CACA A ARTE SCOUT 0.4.4 - INSTALACAO
echo ==============================================
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY ( where python >nul 2>nul && set "PY=python" )
if not defined PY (
  echo Python nao encontrado. A tentar instalar com o winget - gratuito e oficial...
  winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
  echo.
  echo Feche esta janela e execute INSTALAR.bat outra vez.
  pause
  exit /b 1
)
%PY% --version
if not exist ".venv\Scripts\python.exe" (
  echo A criar ambiente local .venv ...
  %PY% -m venv .venv
)
echo A instalar dependencias (rapidfuzz)...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt
echo A verificar a instalacao (testes offline)...
".venv\Scripts\python.exe" -m unittest test_engine test_p55_connector test_search_parser test_adapters_040 test_p55_041 test_galerias_044
echo.
echo A criar atalho no Ambiente de Trabalho...
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Caca a Arte Scout.lnk');$s.TargetPath='%~dp0INICIAR_CACA_ARTE_SCOUT.bat';$s.WorkingDirectory='%~dp0';$s.Save()"
echo.
echo Instalacao concluida.
echo  - Para usar: atalho "Caca a Arte Scout" no Ambiente de Trabalho
echo  - Para testar as fontes: TESTAR_FONTES.bat
pause
endlocal
