# -*- coding: utf-8 -*-
"""Adaptadores directos da Caça à Arte Scout (versão 0.4.0).

Cada adaptador recebe uma função ``fetch(url, timeout)`` que devolve bytes.
Assim o mesmo código serve a aplicação, os testes offline (respostas
simuladas) e o diagnóstico real de fontes no computador do utilizador.

Regras seguidas em todos os adaptadores:
* nunca inventar campos: o que não existe fica vazio;
* não contornar login, CAPTCHA nem bloqueios;
* paginação sempre limitada (sem ciclos infinitos);
* uma falha técnica levanta excepção; zero anúncios devolve lista vazia.
"""
import html
import json
import re
import unicodedata
from html.parser import HTMLParser
from urllib.parse import quote, urljoin, urlparse, urlencode

# --------------------------------------------------------------------------
# Utilitários comuns
# --------------------------------------------------------------------------

def fold(value):
    value = unicodedata.normalize("NFKD", str(value or "").casefold())
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", value).strip()


def slugify(value):
    value = fold(value)
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def clean_text(value):
    value = html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))
    return re.sub(r"\s+", " ", value).strip()


def parse_price(text):
    """Extrai um preço em euros de texto livre. Devolve float ou None."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)
    m = re.search(r"(?:€\s?(\d[\d\s.,]*)|(\d[\d\s.,]*)\s?(?:€|eur\b))", str(text), re.I)
    if not m:
        return None
    token = (m.group(1) or m.group(2) or "").replace(" ", "").replace(" ", "")
    token = token.strip(".,")
    if "," in token and "." in token:
        if token.rfind(",") > token.rfind("."):
            token = token.replace(".", "").replace(",", ".")
        else:
            token = token.replace(",", "")
    elif "," in token:
        head, _, tail = token.rpartition(",")
        token = head.replace(",", "") + ("." + tail if len(tail) <= 2 else tail)
    elif token.count(".") >= 1:
        head, _, tail = token.rpartition(".")
        if len(tail) == 3:  # 1.800 -> milhares
            token = token.replace(".", "")
    try:
        return float(token)
    except ValueError:
        return None


def price_text(price):
    if price is None:
        return "Preço não indicado"
    return "€" + format(price, ",.2f").replace(",", "X").replace(".", ",").replace("X", ".")


def artist_in(artist, text):
    """Correspondência estrita (sem acentos/capitalização) do artista no texto."""
    a = fold(artist)
    return bool(a) and a in fold(text)


WANTED_AD = re.compile(r"\b(compro|procuro|procura-se|troco|wanted)\b", re.I)
JUNK_USED = re.compile(
    r"\b(m[oó]vel|mob[ií]lia|sof[aá]|cadeira|mesa de|lou[cç]a|talheres|"
    r"roupa|sapatos|carro|mota|apartamento|moradia|terreno|arrendamento|servi[cç]os)\b",
    re.I,
)


def _walk(obj):
    """Percorre recursivamente estruturas JSON."""
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _walk(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _walk(value)


def _json_after(raw, marker):
    """Lê o objecto/cadeia JSON que se segue a ``marker`` numa página."""
    i = raw.find(marker)
    if i < 0:
        return None
    rest = raw[i + len(marker):].lstrip(" =\t\r\n")
    decoder = json.JSONDecoder()
    try:
        value, _ = decoder.raw_decode(rest)
    except ValueError:
        return None
    if isinstance(value, str):  # estado serializado duas vezes (OLX)
        try:
            value = json.loads(value)
        except ValueError:
            return None
    return value


def _next_data(raw):
    m = re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', raw, re.S | re.I)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except ValueError:
        return None


class _AnchorParser(HTMLParser):
    """Recolhe todas as âncoras com href, texto e posição aproximada."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.anchors = []
        self._stack = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._stack.append({"href": dict(attrs).get("href", ""), "text": [], "pos": self.getpos()})
        elif tag == "img" and self._stack:
            a = dict(attrs)
            self._stack[-1].setdefault("img", a.get("src") or a.get("data-src") or "")
            self._stack[-1]["text"].append(a.get("alt") or "")

    def handle_endtag(self, tag):
        if tag == "a" and self._stack:
            item = self._stack.pop()
            item["text"] = re.sub(r"\s+", " ", " ".join(item["text"])).strip()
            self.anchors.append(item)

    def handle_data(self, data):
        for item in self._stack:
            item["text"].append(data)


def anchors(raw):
    p = _AnchorParser()
    try:
        p.feed(raw)
    except Exception:
        pass
    return p.anchors


def meta_content(raw, *keys):
    for key in keys:
        for pattern in (
            r'<meta\b[^>]*(?:property|name)=["\']' + re.escape(key) + r'["\'][^>]*content=["\']([^"\']*)["\']',
            r'<meta\b[^>]*content=["\']([^"\']*)["\'][^>]*(?:property|name)=["\']' + re.escape(key) + r'["\']',
        ):
            m = re.search(pattern, raw, re.I | re.S)
            if m and m.group(1).strip():
                return html.unescape(m.group(1)).strip()
    return ""


def enrich_detail(item, fetch, timeout=14):
    """Completa um resultado com a ficha individual (og:*, JSON-LD Product).

    Só preenche campos vazios. Devolve (item, texto_da_ficha)."""
    try:
        raw = fetch(item["url"], timeout).decode("utf-8", "replace")
    except Exception:
        return item, ""
    title = meta_content(raw, "og:title", "twitter:title")
    desc = meta_content(raw, "og:description", "description", "twitter:description")
    image = meta_content(raw, "og:image", "twitter:image")
    price = None
    currency = ""
    for block in re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', raw, re.I | re.S):
        try:
            data = json.loads(html.unescape(block))
        except ValueError:
            continue
        for obj in _walk(data):
            typ = obj.get("@type", "")
            typ = typ if isinstance(typ, list) else [typ]
            if not any("Product" in str(t) or "Book" in str(t) or "VisualArtwork" in str(t) for t in typ):
                continue
            title = title or str(obj.get("name") or "")
            desc = desc or str(obj.get("description") or "")
            im = obj.get("image")
            if not image and im:
                image = im[0] if isinstance(im, list) else (im.get("url") if isinstance(im, dict) else im)
            offers = obj.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            if isinstance(offers, dict) and price is None and offers.get("price") not in (None, ""):
                try:
                    price = float(str(offers.get("price")).replace(",", "."))
                    currency = str(offers.get("priceCurrency") or "")
                except ValueError:
                    pass
    if price is None:
        price = parse_price(meta_content(raw, "product:price:amount", "og:price:amount") + " €") \
            if meta_content(raw, "product:price:amount", "og:price:amount") else None
    if not item.get("image") and image:
        item["image"] = urljoin(item["url"], str(image))
    if not item.get("description") and desc:
        item["description"] = clean_text(desc)[:400]
    if (not item.get("title") or item["title"].startswith("Obra de ")) and title:
        item["title"] = clean_text(title)[:220]
    if item.get("price") is None and price is not None:
        item["price"] = price
        item["price_text"] = price_text(price)
        item["currency"] = currency or "EUR"
    return item, clean_text(raw)


def make_item(artist, source, title, url, price=None, image="", description="",
              availability="", shipping="Envio para Portugal por confirmar", **extra):
    item = {
        "artist": artist, "title": clean_text(title)[:220] or url, "price": price,
        "price_text": price_text(price), "currency": "EUR" if price is not None else "",
        "url": url, "image": image or "", "description": clean_text(description)[:400],
        "source": source, "availability": availability or "Confirmar disponibilidade no anúncio",
        "shipping": shipping,
    }
    item.update({k: v for k, v in extra.items() if v not in (None, "")})
    return item


def category_ok(category, text, patterns):
    if category in ("", "Todas"):
        return True
    pattern = patterns.get(category, r".")
    return bool(re.search(fold(pattern), fold(text), re.I))


# --------------------------------------------------------------------------
# OLX Portugal: página pública de pesquisa /ads/q-<termo>/
# --------------------------------------------------------------------------

def _olx_ads_from_state(raw):
    state = _json_after(raw, "window.__PRERENDERED_STATE__")
    if state is None:
        return []
    ads = []
    for obj in _walk(state):
        url = obj.get("url") if isinstance(obj.get("url"), str) else ""
        if obj.get("title") and "/d/anuncio/" in url:
            ads.append(obj)
    return ads


def _olx_photo(photos):
    if not photos:
        return ""
    first = photos[0]
    if isinstance(first, dict):
        first = first.get("link") or first.get("url") or ""
    return str(first).replace("{width}", "600").replace("{height}", "450")


def _olx_price(ad):
    price = ad.get("price")
    if isinstance(price, dict):
        reg = price.get("regularPrice") or {}
        if isinstance(reg, dict) and reg.get("value") not in (None, ""):
            try:
                return float(reg["value"])
            except (TypeError, ValueError):
                pass
        return parse_price(price.get("displayValue"))
    return parse_price(price)


def parse_olx_page(raw):
    """Devolve lista de anúncios normalizados (sem filtro de artista)."""
    out = []
    for ad in _olx_ads_from_state(raw):
        loc = ad.get("location") or {}
        out.append({
            "id": str(ad.get("id") or ""), "title": ad.get("title", ""),
            "url": urljoin("https://www.olx.pt", ad.get("url", "")),
            "description": clean_text(ad.get("description", "")),
            "price": _olx_price(ad), "image": _olx_photo(ad.get("photos")),
            "published": ad.get("createdTime") or ad.get("lastRefreshTime") or "",
            "location": loc.get("cityName", "") if isinstance(loc, dict) else "",
        })
    if out:
        return out
    # Alternativa HTML: cartões com ligação /d/anuncio/
    seen = set()
    for a in anchors(raw):
        href = a.get("href", "")
        if "/d/anuncio/" not in href or not a["text"]:
            continue
        url = urljoin("https://www.olx.pt", href.split("?")[0])
        if url in seen:
            continue
        seen.add(url)
        pos = raw.find(href)
        ctx = clean_text(raw[pos:pos + 2500]) if pos >= 0 else ""
        m = re.search(r"-ID([A-Za-z0-9]+)\.html", url)
        out.append({"id": m.group(1) if m else "", "title": a["text"], "url": url, "description": "",
                    "price": parse_price(ctx[:400]), "image": a.get("img", ""), "published": "", "location": ""})
    return out


def search_olx(artist, category, limit, fetch, patterns, max_pages=3):
    base = "https://www.olx.pt/ads/q-" + quote(slugify(artist)) + "/"
    results, seen = [], set()
    pages_ok = 0
    last_error = None
    for page in range(1, max_pages + 1):
        url = base if page == 1 else base + "?page=" + str(page)
        try:
            raw = fetch(url, 15).decode("utf-8", "replace")
        except Exception as exc:
            last_error = exc
            break
        if re.search(r"captcha|verify you are human", raw, re.I) and "/d/anuncio/" not in raw:
            raise RuntimeError("OLX apresentou página de verificação (CAPTCHA); não contornado")
        pages_ok += 1
        ads = parse_olx_page(raw)
        new = 0
        for ad in ads:
            if ad["url"] in seen:
                continue
            seen.add(ad["url"])
            new += 1
            text = ad["title"] + " " + ad["description"]
            if not artist_in(artist, ad["title"]) and not artist_in(artist, ad["description"][:300]):
                continue
            if WANTED_AD.search(ad["title"]) or JUNK_USED.search(ad["title"]):
                continue
            if not category_ok(category, text, patterns):
                continue
            results.append(make_item(
                artist, "OLX", ad["title"], ad["url"], ad["price"], ad["image"], ad["description"],
                availability="Anúncio activo na pesquisa OLX", listing_id=ad["id"],
                published=ad["published"], location=ad["location"]))
        if new == 0 or len(results) >= limit:
            break
    if pages_ok == 0:
        raise RuntimeError("OLX inacessível: %s" % last_error)
    return results[:limit]


# --------------------------------------------------------------------------
# CustoJusto: /portugal/q/<termo>
# --------------------------------------------------------------------------

_CJ_AD = re.compile(r"(?:https?://www\.custojusto\.pt)?/[a-z0-9-]+/[a-z0-9/-]+-(\d{6,})(?:[/?#]|$)", re.I)


def parse_custojusto_page(raw):
    out, seen = [], set()
    data = _next_data(raw)
    if data:
        for obj in _walk(data):
            title = obj.get("title") or obj.get("subject")
            url = obj.get("url") or obj.get("link") or obj.get("href")
            if not (isinstance(title, str) and isinstance(url, str) and _CJ_AD.search(url)):
                continue
            full = urljoin("https://www.custojusto.pt", url)
            if full in seen:
                continue
            seen.add(full)
            img = obj.get("image") or obj.get("thumbnail") or obj.get("images") or ""
            if isinstance(img, list):
                img = img[0] if img else ""
            if isinstance(img, dict):
                img = img.get("url") or img.get("src") or ""
            price = obj.get("price")
            price = parse_price(price) if not isinstance(price, (int, float)) else float(price)
            if price is None and isinstance(obj.get("price"), dict):
                price = parse_price(obj["price"].get("value") or obj["price"].get("label"))
            out.append({"id": _CJ_AD.search(url).group(1), "title": title, "url": full,
                        "description": clean_text(obj.get("description") or obj.get("body") or ""),
                        "price": price, "image": str(img or "")})
    if out:
        return out
    for a in anchors(raw):
        href = a.get("href", "")
        m = _CJ_AD.search(href)
        if not m or not a["text"]:
            continue
        full = urljoin("https://www.custojusto.pt", href.split("?")[0])
        if full in seen:
            continue
        seen.add(full)
        pos = raw.find(href)
        ctx = clean_text(raw[pos:pos + 2000]) if pos >= 0 else ""
        out.append({"id": m.group(1), "title": a["text"], "url": full, "description": "",
                    "price": parse_price(ctx[:300]), "image": a.get("img", "")})
    return out


def search_custojusto(artist, category, limit, fetch, patterns, max_pages=2):
    base = "https://www.custojusto.pt/portugal/q/" + quote(fold(artist))
    results, seen, pages_ok, last_error = [], set(), 0, None
    for page in range(1, max_pages + 1):
        url = base if page == 1 else base + "?o=" + str(page)
        try:
            raw = fetch(url, 15).decode("utf-8", "replace")
        except Exception as exc:
            last_error = exc
            break
        pages_ok += 1
        new = 0
        for ad in parse_custojusto_page(raw):
            if ad["url"] in seen:
                continue
            seen.add(ad["url"])
            new += 1
            # A pesquisa do CustoJusto é muito permissiva (devolve casas e carros):
            # exigir o nome do artista no título ou descrição.
            if not (artist_in(artist, ad["title"]) or artist_in(artist, ad["description"])):
                continue
            if WANTED_AD.search(ad["title"]) or JUNK_USED.search(ad["title"]):
                continue
            if not category_ok(category, ad["title"] + " " + ad["description"], patterns):
                continue
            results.append(make_item(artist, "CustoJusto", ad["title"], ad["url"], ad["price"], ad["image"],
                                     ad["description"], availability="Anúncio activo na pesquisa CustoJusto",
                                     listing_id=ad["id"]))
        if new == 0 or len(results) >= limit:
            break
    if pages_ok == 0:
        raise RuntimeError("CustoJusto inacessível: %s" % last_error)
    return results[:limit]


# --------------------------------------------------------------------------
# Galeria São Mamede: /listagem/artistas/<slug> -> /listagem/obras-de-arte/<slug>
# --------------------------------------------------------------------------

SOLD = re.compile(r"\b(vendid[oa]|esgotad[oa]|indispon[ií]vel|n[aã]o dispon[ií]vel|sold|out of stock)\b", re.I)


def parse_saomamede_artist(raw, page_url):
    works, seen = [], set()
    for a in anchors(raw):
        href = a.get("href", "")
        if "/listagem/obras-de-arte/" not in href:
            continue
        url = urljoin(page_url, href).split("#")[0]
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        if not slug or slug == "obras-de-arte" or url in seen:
            continue
        seen.add(url)
        pos = raw.find(href)
        # O cartão termina onde começa a ligação da obra seguinte; assim o
        # "Vendido" de uma obra não contamina a vizinha.
        nxt = raw.find("/listagem/obras-de-arte/", pos + len(href)) if pos >= 0 else -1
        end = nxt if nxt > 0 else pos + 1500
        own = raw[pos:min(end, pos + 1500)] if pos >= 0 else ""
        ctx_raw = raw[max(0, pos - 300):min(end, pos + 1500)] if pos >= 0 else ""
        ctx = clean_text(own)
        img = a.get("img") or ""
        if not img:
            m = re.search(r'<img[^>]+(?:data-src|src)=["\']([^"\']+)["\']', ctx_raw, re.I)
            img = m.group(1) if m else ""
        works.append({"url": url, "title": a["text"], "context": ctx,
                      "image": urljoin(page_url, html.unescape(img)) if img else "",
                      "sold": bool(SOLD.search(ctx))})
    return works


def search_sao_mamede(artist, category, limit, fetch, patterns, enrich=True):
    page_url = "https://www.saomamede.com/listagem/artistas/" + slugify(artist)
    try:
        raw = fetch(page_url, 18).decode("utf-8", "replace")
    except Exception as exc:
        if "HTTP 404" in str(exc):
            return []  # artista não representado pela galeria
        raise
    works = parse_saomamede_artist(raw, page_url)
    if not works:
        if re.search(r"obras de arte", raw, re.I):
            return []  # página do artista existe, sem obras listadas
        raise RuntimeError("Página do artista sem secção de obras (artista inexistente ou site alterado)")
    results = []
    for w in works:
        if w["sold"]:
            continue
        title = w["title"] or w["url"].rsplit("/", 1)[-1].replace("-", " ").capitalize()
        item = make_item(artist, "Galeria São Mamede", title, w["url"], parse_price(w["context"][:200]),
                         w["image"], w["context"][:300], availability="Disponível segundo a página do artista")
        if enrich and (not item["image"] or item["price"] is None):
            item, _ = enrich_detail(item, fetch)
        if not category_ok(category, item["title"] + " " + item["description"], patterns):
            continue
        results.append(item)
        if len(results) >= limit:
            break
    return results


# --------------------------------------------------------------------------
# Livrarias com formulário de pesquisa: descoberta automática do formulário
# --------------------------------------------------------------------------

class _FormParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms = []
        self._cur = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form":
            self._cur = {"action": a.get("action") or "", "method": (a.get("method") or "get").lower(),
                         "inputs": [], "text": []}
        elif self._cur is not None and tag in ("input", "select"):
            self._cur["inputs"].append({"tag": tag, "type": (a.get("type") or "text").lower(),
                                        "name": a.get("name") or "", "value": a.get("value") or "",
                                        "placeholder": a.get("placeholder") or "", "id": a.get("id") or ""})

    def handle_endtag(self, tag):
        if tag == "form" and self._cur is not None:
            self.forms.append(self._cur)
            self._cur = None


def discover_search_urls(raw, base, term):
    """Gera URLs de pesquisa GET a partir dos formulários públicos da página."""
    p = _FormParser()
    try:
        p.feed(raw)
    except Exception:
        pass
    urls = []
    for form in p.forms:
        if form["method"] != "get":
            continue
        texts = [i for i in form["inputs"] if i["tag"] == "input" and i["type"] in ("text", "search") and i["name"]]
        if not texts:
            continue
        # escolher o campo com mais "cara" de pesquisa
        def score(i):
            s = (i["name"] + " " + i["placeholder"] + " " + i["id"]).casefold()
            return any(k in s for k in ("pesq", "search", "query", "busca", "termo", "q", "s"))
        texts.sort(key=lambda i: not score(i))
        field = texts[0]
        params = [(i["name"], i["value"]) for i in form["inputs"]
                  if i["tag"] == "input" and i["type"] == "hidden" and i["name"]]
        params.append((field["name"], term))
        action = urljoin(base.rstrip("/") + "/", form["action"] or "")
        if urlparse(action).netloc.replace("www.", "") != urlparse(base).netloc.replace("www.", ""):
            continue
        urls.append(action.split("?")[0] + "?" + urlencode(params))
    return list(dict.fromkeys(urls))


MISSING_QUERY = re.compile(r"falta a pesquisa|pesquisa vazia|no search term|introduza (um|o) termo", re.I)


def search_bookshop_auto(artist, category, source, base, fetch, card_parser, patterns,
                         fallback_urls=(), limit=50, enrich_max=12):
    """Pesquisa uma livraria: formulário descoberto -> URLs conhecidos -> enriquecimento."""
    errors, tried, found = [], [], []
    candidates = []
    try:
        home = fetch(base, 15).decode("utf-8", "replace")
        candidates.extend(discover_search_urls(home, base, artist))
    except Exception as exc:
        errors.append("página inicial: %s" % exc)
    candidates.extend(u for u in fallback_urls if u not in candidates)
    loose = []
    ok_pages = 0
    for url in candidates:
        tried.append(url)
        try:
            raw = fetch(url, 15).decode("utf-8", "replace")
        except Exception as exc:
            errors.append("%s: %s" % (url, exc))
            continue
        found = card_parser(raw, base, artist)
        if not found and MISSING_QUERY.search(clean_text(raw)[:20000]):
            errors.append("%s: parâmetro de pesquisa não reconhecido pelo site" % url)
            continue
        ok_pages += 1
        if found:
            break
        if not loose:
            loose = card_parser(raw, base, "")  # cartões sem o nome do artista
    if not found and loose:
        # O cartão pode não repetir o autor: confirmar na ficha individual.
        for item in loose[:enrich_max]:
            item, text = enrich_detail(dict(item), fetch)
            if artist_in(artist, text):
                found.append(item)
    if not found and ok_pages == 0:
        raise RuntimeError("Fonte indisponível ou pesquisa não reconhecida: " + "; ".join(errors[-4:]))
    results = []
    for i, it in enumerate(found):
        item = make_item(artist, source, it.get("title", ""), it["url"], it.get("price"), it.get("image", ""),
                         it.get("description", ""), availability="Encontrado no catálogo; confirmar na ficha")
        if i < enrich_max and (not item["image"] or item["price"] is None):
            item, _ = enrich_detail(item, fetch)
        if not category_ok(category, item["title"] + " " + item["description"], patterns):
            # numa livraria tudo é livro: aceitar "Livros" mesmo sem palavra-chave
            if category != "Livros":
                continue
        results.append(item)
    results.sort(key=lambda x: (x["price"] is None, x["price"] or 0))
    return results[:limit]


# --------------------------------------------------------------------------
# Galerias de arte com motor directo (0.4.4) - estrutura verificada nos sites
# reais em 22-11-2026 a partir do navegador do utilizador.
# --------------------------------------------------------------------------

def _get_json(fetch, url, timeout=15):
    return json.loads(fetch(url, timeout).decode("utf-8", "replace"))


def search_shopify_store(artist, category, limit, fetch, patterns, base, source):
    """Loja Shopify genérica (Underdogs, ...): colecção do artista e/ou pesquisa da loja."""
    base = base.rstrip("/")
    products, errors, ok = {}, [], 0
    for page in range(1, 5):
        try:
            data = _get_json(fetch, f"{base}/collections/{slugify(artist)}/products.json?limit=250&page={page}")
            ok += 1
        except Exception as exc:
            errors.append(str(exc)); break
        rows = data.get("products") or []
        for p in rows:
            products[p.get("handle")] = p
        if len(rows) < 250:
            break
    if not products:
        try:
            data = _get_json(fetch, f"{base}/search/suggest.json?q={quote(artist)}&resources[type]=product&resources[limit]=10")
            ok += 1
            for p in data.get("resources", {}).get("results", {}).get("products", []):
                products[p.get("handle") or p.get("url")] = p
        except Exception as exc:
            errors.append(str(exc))
    if ok == 0:
        raise RuntimeError(f"{source} inacessível: " + "; ".join(errors[:2]))
    out = []
    for p in products.values():
        text = " ".join(str(p.get(k, "")) for k in ("title", "body_html", "body", "vendor", "product_type"))
        if not artist_in(artist, text):
            continue
        if "variants" in p:
            variants = [v for v in p.get("variants") or [] if v.get("available")]
            if not variants:
                continue
            price = min((float(v["price"]) for v in variants if v.get("price")), default=None)
            imgs = p.get("images") or []
            image = imgs[0].get("src", "") if imgs and isinstance(imgs[0], dict) else ""
            url = f"{base}/products/{p.get('handle')}"
        else:
            if p.get("available") is False:
                continue
            price = parse_price(str(p.get("price", "")) + " €")
            im = p.get("featured_image") or p.get("image") or ""
            image = im.get("url", "") if isinstance(im, dict) else str(im)
            url = urljoin(base + "/", (p.get("url") or "").split("?")[0])
        if image.startswith("//"):
            image = "https:" + image
        if not category_ok(category, text, patterns):
            continue
        out.append(make_item(artist, source, p.get("title", ""), url, price, image, clean_text(p.get("body_html") or p.get("body") or ""),
                             availability="Disponível na loja online"))
    out.sort(key=lambda x: (x["price"] is None, x["price"] or 0))
    return out[:limit]


def search_woocommerce_store(artist, category, limit, fetch, patterns, base, source):
    """Loja WooCommerce com Store API pública (TwoArt, ...)."""
    base = base.rstrip("/")
    data = _get_json(fetch, f"{base}/wp-json/wc/store/v1/products?search={quote(artist)}&per_page=100")
    out = []
    for p in data if isinstance(data, list) else []:
        text = clean_text(p.get("name", "") + " " + p.get("description", "") + " " + p.get("short_description", ""))
        if not artist_in(artist, text) or p.get("is_in_stock") is False:
            continue
        pr = p.get("prices") or {}
        price = None
        try:
            price = int(pr.get("price")) / (10 ** int(pr.get("currency_minor_unit", 2)))
        except (TypeError, ValueError):
            pass
        imgs = p.get("images") or []
        if not category_ok(category, text, patterns):
            continue
        out.append(make_item(artist, source, clean_text(p.get("name", "")), p.get("permalink", ""), price,
                             imgs[0].get("src", "") if imgs else "", text, availability="Em stock na loja online"))
    out.sort(key=lambda x: (x["price"] is None, x["price"] or 0))
    return out[:limit]


def search_cps(artist, category, limit, fetch, patterns, max_pages=5):
    """Centro Português de Serigrafia: /pt/search/?q=<artista>."""
    base = "https://www.cps.pt"
    out, seen = [], set()
    for page in range(1, max_pages + 1):
        url = f"{base}/pt/search/?q={quote(artist)}" + (f"&page={page}" if page > 1 else "")
        raw = fetch(url, 18).decode("utf-8", "replace")
        new = 0
        for m in re.finditer(r'<a href="(/pt/loja/[^"?#]+)">(.*?)</a>', raw, re.S):
            href, inner = m.group(1), m.group(2)
            if "ws-item-title" not in inner or href in seen:
                continue
            seen.add(href); new += 1
            title = clean_text((re.search(r'ws-item-category">(.*?)</div>', inner, re.S) or [None, ""])[1])
            who = clean_text((re.search(r'ws-item-title">(.*?)</h3>', inner, re.S) or [None, ""])[1])
            if not artist_in(artist, who + " " + title) or re.search(r"esgotad", clean_text(inner), re.I):
                continue
            pm = re.search(r'price-customer">(.*?)</span>', inner, re.S)
            img = re.search(r'<img src="([^"]+)"', inner)
            if not category_ok(category, title + " serigrafia", patterns):
                continue
            out.append(make_item(artist, "Centro Português de Serigrafia", title, base + href,
                                 parse_price(clean_text(pm.group(1)) if pm else ""),
                                 base + img.group(1) if img else "", f"{who}. Preço para sócios pode ser inferior.",
                                 availability="Disponível na loja do CPS"))
        if new == 0 or f"page={page + 1}" not in raw:
            break
    return out[:limit]


def search_art4all(artist, category, limit, fetch, patterns):
    """Art4All (OpenCart): index.php?route=product/search."""
    base = "https://www.art4all.pt"
    raw = fetch(f"{base}/index.php?route=product/search&search={quote(artist)}&limit=100", 18).decode("utf-8", "replace")
    out, seen = [], set()
    for block in raw.split('class="product-block-inner"')[1:]:
        m = re.search(r'href="([^"]*route=product/product[^"]*product_id=(\d+)[^"]*)"', block)
        if not m or m.group(2) in seen:
            continue
        seen.add(m.group(2))
        name = re.search(r'title="([^"]+)"', block)
        title = html.unescape(name.group(1)) if name else ""
        if not artist_in(artist, title) or re.search(r"esgotad|indispon", clean_text(block[:4000]), re.I):
            continue
        pm = re.search(r'class="price[^"]*">(.*?)</', block, re.S)
        img = re.search(r'<img src="([^"]+)"', block)
        if not category_ok(category, title + " serigrafia", patterns):
            continue
        url = f"{base}/index.php?route=product/product&product_id={m.group(2)}"
        out.append(make_item(artist, "Art4All", title, url, parse_price(clean_text(pm.group(1)) if pm else ""),
                             img.group(1) if img else "", "", availability="Disponível na loja Art4All", listing_id=m.group(2)))
    out.sort(key=lambda x: (x["price"] is None, x["price"] or 0))
    return out[:limit]


def search_culturas(artist, category, limit, fetch, patterns):
    """Culturas Galeria de Arte: /artistas -> artistas-<id>-<Nome> -> grelha de obras."""
    base = "https://www.culturas.pt/"
    raw = fetch(base + "artistas", 18).decode("utf-8", "replace")
    page = None
    for href in re.findall(r"href=['\"](artistas-\d+-[^'\"]+)['\"]", raw):
        if fold(html.unescape(href.split("-", 2)[2])) == fold(artist):
            page = href
            break
    if not page:
        return []  # artista não representado pela galeria
    raw = fetch(base + quote(html.unescape(page)), 18).decode("utf-8", "replace")
    out = []
    for block in raw.split("class='grelha-items'")[1:]:
        m = re.search(r"href='(detalhes-(\d+)-[^']*)'", block)
        if not m:
            continue
        title = clean_text((re.search(r"<h3 class='sub1'>(.*?)</h3>", block, re.S) or [None, ""])[1])
        tecnica = clean_text((re.search(r"<span class='texto'>(.*?)</span><br", block, re.S) or [None, ""])[1])
        pm = re.search(r"parte2_1_1'><span class='texto'>(.*?)</span>", block, re.S)
        img = re.search(r"<img src='(obras/[^']+)'", block)
        price_txt = clean_text(pm.group(1)) if pm else ""
        if re.search(r"vendid|reservad", price_txt + block[:3000], re.I):
            continue
        if not category_ok(category, title + " " + tecnica, patterns):
            continue
        out.append(make_item(artist, "Culturas Galeria", title, base + quote(html.unescape(m.group(1))),
                             parse_price(price_txt), base + img.group(1) if img else "", tecnica,
                             availability="Disponível na galeria", listing_id=m.group(2)))
    return out[:limit]


def search_wordpress_pages(artist, category, limit, fetch, patterns, base, source):
    """Galerias sem loja online (Galeria 111, In7Artes): páginas que mencionam o artista."""
    base = base.rstrip("/")
    data = _get_json(fetch, f"{base}/wp-json/wp/v2/search?search={quote(artist)}&per_page=20")
    out = []
    for p in data if isinstance(data, list) else []:
        title = clean_text(p.get("title", ""))
        if not artist_in(artist, title):
            continue
        out.append(make_item(artist, source, title, p.get("url", ""), None, "",
                             "Página da galeria (sem preço publicado; pedir informação)",
                             availability="Sem venda online: contactar a galeria"))
    return out[:limit]
