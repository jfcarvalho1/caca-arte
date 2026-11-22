# -*- coding: utf-8 -*-
"""Teste REAL de todas as fontes (duplo clique). Gera um ZIP na pasta diagnostico."""
import os, subprocess, sys
here = os.path.dirname(os.path.abspath(__file__))
os.chdir(here)
venv = os.path.join(here, ".venv", "Scripts", "python.exe")
exe = venv if os.path.exists(venv) else sys.executable
print("Teste real das fontes (Arte, Livros, Usados). Demora 5 a 10 minutos; não feche esta janela.")
subprocess.call([exe, os.path.join(here, "diagnostico_fontes.py"), "--area", "todas"])
