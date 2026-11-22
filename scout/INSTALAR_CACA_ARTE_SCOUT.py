# -*- coding: utf-8 -*-
"""Instalador da Caça à Arte Scout (duplo clique).

É um ficheiro Python e não .bat: o Controlo Inteligente de Aplicações do
Windows bloqueia .bat vindos da Internet, mas não bloqueia .py.

O que faz:
1. cria o ambiente local .venv nesta pasta (só na primeira vez);
2. instala os requisitos gratuitos (rapidfuzz, certifi) se houver Internet;
3. corre os testes automáticos;
4. cria/actualiza o atalho "Caca a Arte Scout" no Ambiente de Trabalho.
Não altera definições do Windows nem apaga ficheiros.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
WIN = os.name == "nt"
VENV_PY = os.path.join(HERE, ".venv", "Scripts" if WIN else "bin", "python.exe" if WIN else "python")
TESTS = ["test_engine", "test_p55_connector", "test_search_parser", "test_adapters_040",
         "test_p55_041", "test_galerias_044"]


def step(text):
    print("\n== " + text)


def main():
    print("=" * 56)
    print(" CAÇA À ARTE SCOUT - INSTALAÇÃO")
    print("=" * 56)
    print("Python:", sys.version.split()[0], "em", sys.executable)
    if sys.version_info < (3, 10):
        print("É preciso Python 3.10 ou mais recente (gratuito em python.org).")
        return 1

    step("Ambiente local (.venv)")
    if os.path.exists(VENV_PY):
        print("Já existe.")
    else:
        subprocess.check_call([sys.executable, "-m", "venv", ".venv"])
        print("Criado.")

    step("Requisitos (rapidfuzz, certifi)")
    code = subprocess.call([VENV_PY, "-m", "pip", "install", "--disable-pip-version-check", "-q", "-r", "requirements.txt"])
    print("Instalados." if code == 0 else "Sem Internet ou falha no pip: a Scout funciona na mesma, com recursos básicos.")

    step("Testes automáticos")
    code = subprocess.call([VENV_PY, "-m", "unittest", "-q"] + TESTS)
    print("Testes aprovados." if code == 0 else "ATENÇÃO: há testes falhados (ver acima).")

    if WIN:
        step("Atalho no Ambiente de Trabalho")
        lnk_script = (
            "$d=[Environment]::GetFolderPath('Desktop');"
            "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($d+'\\Caca a Arte Scout.lnk');"
            f"$s.TargetPath='{VENV_PY}';"
            f"$s.Arguments='\"{os.path.join(HERE, 'Caca_Arte_Scout.py')}\"';"
            f"$s.WorkingDirectory='{HERE}';"
            "$s.Description='Caça à Arte Scout';"
            "$s.Save()"
        )
        code = subprocess.call(["powershell", "-NoProfile", "-Command", lnk_script])
        print("Atalho 'Caca a Arte Scout' criado." if code == 0 else
              "Não foi possível criar o atalho: use ABRIR_CACA_ARTE_SCOUT.py nesta pasta.")

    print("\nInstalação concluída.")
    print(" - Usar: atalho 'Caca a Arte Scout' (ou ABRIR_CACA_ARTE_SCOUT.py)")
    print(" - Testar fontes reais: TESTAR_FONTES.py")
    return 0


if __name__ == "__main__":
    try:
        rc = main()
    except Exception as exc:
        print("\nERRO:", exc)
        rc = 1
    input("\nPrima Enter para fechar...")
    sys.exit(rc)
