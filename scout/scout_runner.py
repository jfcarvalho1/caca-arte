# -*- coding: utf-8 -*-
"""Executor automático da Caça à Arte Scout (GitHub Actions ou qualquer PC).

Pesquisa os artistas seguidos nas fontes com motor directo das três áreas
(Arte, Livros, Usados), junta com os resultados anteriores e grava
docs/data/resultados.json, que a app do iPhone/iPad lê.

- Anúncios novos ficam marcados (primeira vez vistos nesta execução).
- Anúncios que deixaram de aparecer numa fonte que respondeu bem são
  retirados (vendidos ou removidos); se a fonte falhou, mantêm-se.
- Alertas Telegram opcionais: variáveis TELEGRAM_TOKEN e TELEGRAM_CHAT_ID.

Uso:  python scout/scout_runner.py [--extra "Nome do Artista"] [--max-minutos 50]
"""
import argparse
import hashlib
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import Caca_Arte_Scout as app  # noqa: E402

DATA_DIR = ROOT / "docs" / "data"
RESULTS = DATA_DIR / "resultados.json"
EXTRA_ARTISTS = DATA_DIR / "artistas_extra.json"

# Só fontes com motor directo: os motores de pesquisa (Bing/DDG/Brave)
# bloqueiam pedidos automáticos e só gastariam tempo.
AREAS = {
    "Arte": ["P55.art", "Galeria São Mamede", "Underdogs Gallery", "Centro Português de Serigrafia",
             "Art4All", "Culturas Galeria", "TWOART Gallery", "Galeria 111", "In7Artes"],
    "Livros": ["Alfarrabista Manuel Ferreira", "Livraria Alfarrabista Liliana Queiroz", "Livraria Sá da Costa"],
    "Usados": ["OLX", "CustoJusto"],
}
KEEP_FIELDS = ("artist", "title", "price", "price_text", "currency", "url", "image", "description",
               "source", "availability", "listing_id", "published", "location")


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def key_of(url):
    return hashlib.sha1(app.canonical_key(url or "").encode("utf-8")).hexdigest()[:16]


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def no_engine_fallback(name, category, source, limit):
    # No servidor não se recorre aos motores de pesquisa (bloqueiam robôs).
    raise RuntimeError("motor directo falhou; sem recurso a motores de pesquisa no servidor")


def telegram(items):
    token, chat = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat and items):
        return 0
    sent = 0
    for it in items[:25]:
        text = f"🎨 Novo: {it['artist']}\n{it['title']}\n{it.get('price_text') or ''} · {it['source']}\n{it['url']}"
        data = urllib.parse.urlencode({"chat_id": chat, "text": text, "disable_web_page_preview": "false"}).encode()
        try:
            urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data=data, timeout=15).read()
            sent += 1
        except Exception as exc:
            print("Telegram falhou:", type(exc).__name__)
            break
        time.sleep(0.5)
    if len(items) > 25:
        try:
            data = urllib.parse.urlencode({"chat_id": chat, "text": f"… e mais {len(items) - 25} novidades na app Caça à Arte."}).encode()
            urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data=data, timeout=15).read()
        except Exception:
            pass
    return sent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--extra", default="", help="artista adicional a pesquisar (fica seguido)")
    ap.add_argument("--so-extra", action="store_true", help="pesquisar só o artista adicional")
    ap.add_argument("--max-minutos", type=float, default=50)
    args = ap.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    app.search_external = no_engine_fallback
    app.time.sleep = lambda s: None
    started = time.time()
    run_at = now_iso()

    extras = load_json(EXTRA_ARTISTS, [])
    import re as _re
    extra = " ".join(_re.sub(r"[^\w\s.'-]", " ", args.extra).split())[:60]
    if extra and extra.casefold() not in [a.casefold() for a in app.ARTISTS + extras]:
        extras.append(extra)
        EXTRA_ARTISTS.write_text(json.dumps(extras, ensure_ascii=False, indent=1), encoding="utf-8")
    artists = [extra] if (args.so_extra and extra) else app.ARTISTS + extras

    old = load_json(RESULTS, {})
    old_items = {it["key"]: it for it in old.get("items", [])}
    found, status = {}, []
    ok_pairs = set()
    for area, sources in AREAS.items():
        for source in sources:
            st = {"area": area, "source": source, "ok": 0, "failed": 0, "results": 0, "errors": []}
            for artist in artists:
                if time.time() - started > args.max_minutos * 60:
                    st["errors"].append("tempo máximo atingido")
                    break
                try:
                    rows = app.search_one(source, artist, "Todas", 60, [])
                except Exception as exc:
                    st["failed"] += 1
                    if len(st["errors"]) < 3:
                        st["errors"].append(f"{artist}: {type(exc).__name__}: {str(exc)[:160]}")
                    continue
                st["ok"] += 1
                ok_pairs.add((source, artist.casefold()))
                for r in rows:
                    if not r.get("url"):
                        continue
                    k = key_of(r["url"])
                    item = {f: r.get(f) for f in KEEP_FIELDS if r.get(f) not in (None, "")}
                    item.update(key=k, area=area, artist=artist)
                    found.setdefault(k, item)
                st["results"] += len(rows)
            status.append(st)
            print(f"{area:7} {source:40} ok={st['ok']:3} falhas={st['failed']:3} resultados={st['results']}")

    items, new_items = [], []
    for k, it in found.items():
        prev = old_items.get(k)
        it["first_seen"] = prev.get("first_seen", run_at) if prev else run_at
        it["last_seen"] = run_at
        if prev and prev.get("price") not in (None, it.get("price")) and it.get("price") is not None:
            it["previous_price"] = prev["price"]
        if not prev:
            new_items.append(it)
        items.append(it)
    kept = 0
    for k, prev in old_items.items():
        if k in found:
            continue
        # A fonte não respondeu para este artista: manter o anúncio anterior.
        if (prev.get("source"), str(prev.get("artist", "")).casefold()) not in ok_pairs:
            items.append(prev)
            kept += 1

    items.sort(key=lambda x: (x.get("first_seen", ""), x.get("price") or 0), reverse=True)
    out = {
        "app": "Caça à Arte Scout", "version": app.VERSION, "updated": run_at,
        "duration_s": round(time.time() - started), "artists": app.ARTISTS + extras,
        "new_count": len(new_items), "status": status, "items": items,
    }
    RESULTS.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"\n{len(items)} anúncios ({len(new_items)} novos, {kept} mantidos de fontes que falharam) em {out['duration_s']} s")
    first_run = not old_items
    sent = 0 if first_run else telegram(new_items)  # na 1.ª execução não inunda o Telegram
    if sent:
        print("Alertas Telegram enviados:", sent)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(f"## Caça à Arte Scout\n{len(items)} anúncios, {len(new_items)} novos.\n\n| Área | Fonte | OK | Falhas | Resultados |\n|---|---|---|---|---|\n")
            for st in status:
                f.write(f"| {st['area']} | {st['source']} | {st['ok']} | {st['failed']} | {st['results']} |\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
