"""Registo explícito de adaptadores Scout. Estado não equivale a validação em produção."""
import json
from pathlib import Path

_REGISTRY = json.loads((Path(__file__).parent / "sources.json").read_text(encoding="utf-8"))

def list_sources(area=None):
    return {name: data for name, data in _REGISTRY.items()
            if area is None or area in data.get("areas", [])}

def get_source(name):
    if name not in _REGISTRY:
        raise KeyError(f"Fonte desconhecida: {name}")
    return dict(_REGISTRY[name])
