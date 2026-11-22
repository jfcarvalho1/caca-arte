import unicodedata, re
try:
    from rapidfuzz import fuzz
except ImportError:
    fuzz=None

ARTISTS = [
 "Cruzeiro Seixas", "Noronha da Costa", "José de Guimarães",
 "Manuel Cargaleiro", "Luzia Lage", "Alfredo Luz", "Sofia Areal",
 "Paula Rego", "Nadir Afonso", "Júlio Pomar", "Júlio Resende",
 "João Cutileiro", "Kiki Lima",
]
def _variants(name):
    # A pesquisa deve reconhecer acentos, capitalização e pequenas diferenças
    # tipográficas sem alterar o nome original apresentado ao utilizador.
    base = str(name or "").strip()
    folded = unicodedata.normalize("NFKD", base)
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    values = [base, base.title(), folded, folded.title()]
    if base == "Cruzeiro Seixas":
        values += ["Cruzeiro de Seixas"]
    return list(dict.fromkeys(v for v in values if v))

ALIASES = {name: _variants(name) for name in ARTISTS}
def fold(value):
    value=unicodedata.normalize("NFKD",str(value or "").casefold())
    value="".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"\s+"," ",value).strip()
def artist_match_score(artist,text):
    hay=fold(text); variants=ALIASES.get(artist,[artist])
    scores=[]
    for name in variants:
        needle=fold(name)
        if needle and needle in hay: return 100
        if fuzz:
            scores.append(fuzz.partial_ratio(needle,hay))
        else:
            scores.append(0)
    return max(scores or [0])
