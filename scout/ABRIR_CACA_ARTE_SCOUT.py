# -*- coding: utf-8 -*-
"""Abre a Caça à Arte Scout (duplo clique).

Substitui o INICIAR_CACA_ARTE_SCOUT.bat, que o Controlo Inteligente de
Aplicações do Windows bloqueia por ser um .bat vindo de um ZIP da Internet.
Usa o Python do ambiente .venv desta pasta, se existir."""
import os
import subprocess
import sys

here = os.path.dirname(os.path.abspath(__file__))
os.chdir(here)
venv = os.path.join(here, ".venv", "Scripts", "python.exe")
exe = venv if os.path.exists(venv) else sys.executable
print("A abrir a Caça à Arte Scout... (deixe esta janela aberta enquanto a usa)")
code = subprocess.call([exe, os.path.join(here, "Caca_Arte_Scout.py")])
if code:
    input("\nA Scout terminou com erro. Prima Enter para fechar...")
