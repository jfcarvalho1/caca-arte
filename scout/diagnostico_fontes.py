# -*- coding: utf-8 -*-
"""Diagnóstico REAL das fontes da Caça à Arte Scout.

Corre no computador do utilizador (com Internet). Para cada fonte faz uma
pesquisa verdadeira, mede o que veio, guarda amostras das páginas recebidas
e gera um relatório. Não altera a base de dados da aplicação.

Uso:  python diagnostico_fontes.py [--area arte|livros|usados|todas] [--termo "Nome"]
"""
import argparse
import json
import os
import re
import sys
import time
import traceback
import zipfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import Caca_Arte_Scout as app  # noqa: E402

AREAS = {
    "arte": ("Fontes de arte", "Cruzeiro Seixas"),
    "livros": ("Fontes de livros", "Cruzeiro Seixas"),
    "usados": ("Usados, arte e livros", "Cruzeiro Seixas"),
}

CURRENT = {"source": None, "requests": [], "samples": 0}
SAMPLE_DIR = None


def safe(name):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name)[:40]


def install_probe():
    real_get = app.get

    def probe(url, timeout=12):
        rec = {"url": url, "status": None, "bytes": 0, "error": ""}
        t0 = time.time()
        try:
            data = real_get(url, timeout)
            rec["status"] = "OK"
            rec["bytes"] = len(data)
            if CURRENT["samples"] < 4 and SAMPLE_DIR is not None:
                CURRENT["samples"] += 1
                folder = SAMPLE_DIR / safe(CURRENT["source"])
                folder.mkdir(parents=True, exist_ok=True)
                (folder / ("%02d.html" % CURRENT["samples"])).write_bytes(data[:600000])
                with open(folder / "urls.txt", "a", encoding="utf-8") as f:
                    f.write("%02d %s\n" % (CURRENT["samples"], url))
            return data
        except Exception as exc:
            rec["error"] = "%s: %s" % (type(exc).__name__, exc)
            m = re.search(r"HTTP (\d{3})", str(exc))
            rec["status"] = "HTTP " + m.group(1) if m else "ERRO"
            raise
        finally:
            rec["secs"] = round(time.time() - t0, 1)
            CURRENT["requests"].append(rec)

    app.get = probe


def classify(rows, error, warnings, requests):
    if error:
        e = error.lower()
        if not any(r["status"] == "OK" for r in requests) and re.search(
                r"urlopen error|getaddrinfo|name or service|tunnel connection|connection refused|no route", e):
            kind = "SEM LIGAÇÃO (rede, DNS ou proxy)"
        elif "captcha" in e or "verifica" in e or "bloqueio" in e:
            kind = "BLOQUEADA (CAPTCHA/verificação)"
        elif re.search(r"\b429\b", e):
            kind = "LIMITADA (HTTP 429, demasiados pedidos)"
        elif re.search(r"\b403\b", e):
            kind = "RECUSADA (HTTP 403)"
        elif re.search(r"\b404\b", e):
            kind = "ENDEREÇO NÃO EXISTE (HTTP 404)"
        elif "timed out" in e or "timeout" in e:
            kind = "SEM RESPOSTA (tempo esgotado)"
        elif "formato" in e or "não reconhec" in e or "sem secção" in e:
            kind = "SITE MUDOU (formato não reconhecido)"
        else:
            kind = "FALHA TÉCNICA"
        return "FALHOU", kind
    if rows:
        return ("CONDICIONADA" if warnings else "FUNCIONA"), ("via motor de pesquisa" if warnings else "")
    reached = any(r["status"] == "OK" for r in requests)
    return "SEM RESULTADOS", ("site respondeu, nada encontrado para o termo" if reached else "nenhuma página obtida")


def quality(rows, source):
    if not rows:
        return {}
    domain = app.SOURCE_DOMAINS.get(source) or {"P55.art": "p55.art"}.get(source) or \
        urlparse(app.BOOKSHOP_SOURCES.get(source, "")).netloc.replace("www.", "")
    n = len(rows)
    def pct(k):
        return round(100 * k / n)
    return {
        "com_preco_%": pct(sum(1 for r in rows if r.get("price") is not None)),
        "com_imagem_%": pct(sum(1 for r in rows if r.get("image"))),
        "url_do_proprio_site_%": pct(sum(1 for r in rows if domain and domain in urlparse(r.get("url", "")).netloc)),
        "artista_no_titulo_%": pct(sum(1 for r in rows if app.adapters.artist_in(r.get("artist", ""), r.get("title", "")))),
    }


def main():
    global SAMPLE_DIR
    ap = argparse.ArgumentParser()
    ap.add_argument("--area", default="todas", choices=["arte", "livros", "usados", "todas"])
    ap.add_argument("--termo", default="")
    ap.add_argument("--fonte", default="", help="testar apenas uma fonte (nome exacto)")
    args = ap.parse_args()

    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    out = HERE / "diagnostico" / ("diagnostico_" + stamp)
    SAMPLE_DIR = out / "amostras"
    out.mkdir(parents=True, exist_ok=True)
    install_probe()
    app.time.sleep = lambda s: None  # o ritmo é controlado aqui

    plan = []
    for key in (AREAS if args.area == "todas" else [args.area]):
        group, default_term = AREAS[key]
        for source in app.SOURCE_GROUPS[group]:
            if args.fonte and source != args.fonte:
                continue
            plan.append((key, source, args.termo or default_term))

    print("Caça à Arte Scout %s - diagnóstico real de %d fontes" % (app.VERSION, len(plan)))
    print("Pasta do relatório:", out)
    report = []
    for i, (area, source, term) in enumerate(plan, 1):
        CURRENT.update(source=source, requests=[], samples=0)
        warnings, rows, error = [], [], ""
        t0 = time.time()
        print("[%2d/%d] %-34s ... " % (i, len(plan), source[:34]), end="", flush=True)
        try:
            rows = app.search_one(source, term, "Todas", 20, warnings)
        except Exception as exc:
            error = "%s: %s" % (type(exc).__name__, exc)
        state, detail = classify(rows, error, warnings, CURRENT["requests"])
        entry = {
            "area": area, "fonte": source, "termo": term, "metodo": app.source_method(source),
            "estado": state, "detalhe": detail, "resultados": len(rows), "segundos": round(time.time() - t0, 1),
            "qualidade": quality(rows, source), "erro": error[:1500], "avisos": warnings,
            "pedidos": CURRENT["requests"][:12],
            "exemplos": [{k: r.get(k) for k in ("title", "price_text", "url", "image")} for r in rows[:3]],
        }
        report.append(entry)
        print(state, ("(%d)" % len(rows)) if rows else "", detail)
        time.sleep(1.5)

    (out / "resultado.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    write_markdown(out, report)
    zpath = HERE / "diagnostico" / ("ENVIAR_diagnostico_%s.zip" % stamp)
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in out.rglob("*"):
            if f.is_file():
                z.write(f, f.relative_to(out.parent))
    print("\nRelatório: ", out / "RELATORIO_FONTES.md")
    print("ZIP para enviar ao Claude:", zpath)
    if os.name == "nt":
        try:
            os.startfile(str(zpath.parent))  # abre a pasta no Explorador
        except Exception:
            pass


def write_markdown(out, report):
    from collections import Counter
    c = Counter(e["estado"] for e in report)
    lines = ["# Caça à Arte Scout %s, diagnóstico real das fontes" % app.VERSION, "",
             "Data: %s" % datetime.now().strftime("%d-%m-%Y %H:%M"), "",
             "Resumo: " + ", ".join("%s: %d" % kv for kv in c.most_common()), "",
             "| Área | Fonte | Método | Estado | Resultados | Preço % | Imagem % | Detalhe |",
             "|---|---|---|---|---|---|---|---|"]
    for e in report:
        q = e["qualidade"]
        lines.append("| %s | %s | %s | **%s** | %d | %s | %s | %s |" % (
            e["area"], e["fonte"], e["metodo"], e["estado"], e["resultados"],
            q.get("com_preco_%", ""), q.get("com_imagem_%", ""), (e["detalhe"] or e["erro"][:120]).replace("|", "/")))
    lines += ["", "## Erros completos", ""]
    for e in report:
        if e["erro"] or e["avisos"]:
            lines.append("### " + e["fonte"])
            if e["erro"]:
                lines.append("```\n" + e["erro"] + "\n```")
            for w in e["avisos"]:
                lines.append("- aviso: " + w)
            lines.append("")
    lines += ["", "Notas: FUNCIONA = devolveu anúncios reais. CONDICIONADA = só funcionou pelo motor de pesquisa. ",
              "SEM RESULTADOS = o site respondeu mas não havia nada para o termo (não é avaria). ",
              "As amostras HTML de cada fonte estão na pasta amostras/ para corrigir os motores."]
    (out / "RELATORIO_FONTES.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
    if os.name == "nt":
        input("\nPrima Enter para fechar...")
