# -*- coding: utf-8 -*-
"""Constrói o CacaArteScout.exe NESTE computador (duplo clique).

Não usa o Claude nem nenhum serviço de IA. Só descarrega do PyPI (repositório
público de programas Python) as ferramentas gratuitas e open source:
PyInstaller, rapidfuzz, certifi e truststore.

No fim fica nesta pasta o ficheiro CacaArteScout.exe e um atalho novo no
Ambiente de Trabalho, 'Caca a Arte Scout (exe)' (o atalho antigo fica igual). O .exe usa a mesma pasta data (histórico de pesquisas).

Nota: o Controlo Inteligente de Aplicações do Windows pode bloquear o .exe,
porque não tem assinatura digital (uma assinatura é paga). Se isso acontecer,
continue a usar ABRIR_CACA_ARTE_SCOUT.py, que faz exactamente o mesmo.
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
VENV_PY = os.path.join(HERE, ".venv", "Scripts", "python.exe")
SEP = ";" if os.name == "nt" else ":"


def run(cmd):
    print(">", " ".join(cmd))
    return subprocess.call(cmd)


def main():
    print("=" * 60)
    print(" CAÇA À ARTE SCOUT - CONSTRUIR O .EXE")
    print("=" * 60)
    if not os.path.exists(VENV_PY):
        print("A criar o ambiente .venv ...")
        if run([sys.executable, "-m", "venv", ".venv"]) != 0:
            return 1
    print("\n1/3 A instalar as ferramentas (precisa de Internet, só desta vez)...")
    if run([VENV_PY, "-m", "pip", "install", "--disable-pip-version-check", "-q",
            "-r", "requirements.txt", "pyinstaller"]) != 0:
        print("Falhou a instalação. Verifique a ligação à Internet e tente de novo.")
        return 1

    print("\n2/3 A construir o CacaArteScout.exe (1 a 3 minutos)...")
    build = os.path.join(HERE, "_construcao_exe")
    code = run([VENV_PY, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--console",
                "--name", "CacaArteScout",
                "--distpath", HERE, "--workpath", build, "--specpath", build,
                "--add-data", os.path.join(HERE, "scout_engine", "sources.json") + SEP + "scout_engine",
                "--collect-data", "certifi",
                "--hidden-import", "truststore",
                "--hidden-import", "rapidfuzz",
                os.path.join(HERE, "Caca_Arte_Scout.py")])
    shutil.rmtree(build, ignore_errors=True)
    exe = os.path.join(HERE, "CacaArteScout.exe")
    if code != 0 or not os.path.exists(exe):
        print("A construção falhou (ver mensagens acima).")
        return 1
    print("Construído:", exe)

    if os.name == "nt":
        print("\n3/3 A criar o atalho no Ambiente de Trabalho...")
        ps = ("$d=[Environment]::GetFolderPath('Desktop');"
              "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($d+'\\Caca a Arte Scout (exe).lnk');"
              f"$s.TargetPath='{exe}';$s.WorkingDirectory='{HERE}';"
              "$s.Description='Caça à Arte Scout';$s.Save()")
        run(["powershell", "-NoProfile", "-Command", ps])
    print("\nPronto. Experimente o novo atalho 'Caca a Arte Scout (exe)'.\nO atalho antigo 'Caca a Arte Scout' continua a funcionar como antes.")
    print("Se o Windows bloquear o .exe, use ABRIR_CACA_ARTE_SCOUT.py (faz o mesmo).")
    return 0


if __name__ == "__main__":
    try:
        rc = main()
    except Exception as exc:
        print("\nERRO:", exc)
        rc = 1
    input("\nPrima Enter para fechar...")
    sys.exit(rc)
