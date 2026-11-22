# -*- coding: utf-8 -*-
"""Caça à Arte Scout: pesquisa de obras em fontes seleccionadas."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, quote
from urllib.request import Request, urlopen
from concurrent.futures import ThreadPoolExecutor, as_completed
import json, re, html, threading, webbrowser, time, uuid, unicodedata
from html.parser import HTMLParser
TASKS = {}
TASK_LOCK = threading.Lock()
from urllib.error import HTTPError

# Motor modular Scout. As dependencias são opcionais para permitir diagnóstico claro.
try:
    from scout_engine.database import ResultStore
    _RESULT_STORE = ResultStore()
except Exception as _db_error:
    _RESULT_STORE = None
    _DB_INIT_ERROR = str(_db_error)

try:
    from scout_engine.normalization import artist_match_score
except Exception:
    def artist_match_score(artist, text):
        a = unicodedata.normalize("NFKD", artist.casefold())
        b = unicodedata.normalize("NFKD", text.casefold())
        a = "".join(c for c in a if not unicodedata.combining(c))
        b = "".join(c for c in b if not unicodedata.combining(c))
        return 100 if a in b else 0

try:
    from scout_engine.extraction import extract_page_metadata
except Exception:
    extract_page_metadata = None
from scout_engine import adapters
import logging, os, hashlib
from datetime import datetime, timezone
from pathlib import Path

VERSION = "0.4.4"
APP_DIR = Path(__file__).resolve().parent
(APP_DIR / "data").mkdir(exist_ok=True)
LOG = logging.getLogger("scout")
if not LOG.handlers:
    _h = logging.FileHandler(APP_DIR / "data" / "scout.log", encoding="utf-8")
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    LOG.addHandler(_h)
    LOG.setLevel(logging.INFO)

_HTTP_CACHE = {}
_HTTP_LOCK = threading.Lock()
_HTTP_CACHE_MAX = 400

# Certificados: em alguns Windows o Python recusa sites válidos com
# "certificate has expired" (cadeia antiga no armazém do Windows), embora o
# navegador os aceite. Usa-se primeiro o pacote de autoridades do certifi
# (o mesmo do pip) e só depois o do sistema. A verificação NUNCA é desligada.
import ssl

def _build_ssl_contexts():
    contexts = []
    cafile = None
    try:
        import certifi
        cafile = certifi.where()
    except Exception:
        try:
            from pip._vendor import certifi as _pip_certifi
            cafile = _pip_certifi.where()
        except Exception:
            cafile = None
    if cafile:
        try:
            contexts.append(("certifi", ssl.create_default_context(cafile=cafile)))
        except Exception:
            pass
    # Verificador do próprio Windows (como os navegadores): pacote truststore,
    # incluído no pip. Resolve cadeias antigas que o OpenSSL rejeita.
    try:
        try:
            import truststore
        except Exception:
            from pip._vendor import truststore
        contexts.append(("windows", truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)))
    except Exception:
        pass
    contexts.append(("sistema", ssl.create_default_context()))
    return contexts

_SSL_CONTEXTS = _build_ssl_contexts()

ARTISTS = ["Cruzeiro Seixas", "Noronha da Costa", "José de Guimarães", "Manuel Cargaleiro", "Luzia Lage", "Alfredo Luz", "Sofia Areal", "Paula Rego", "Nadir Afonso", "Júlio Pomar", "Júlio Resende", "João Cutileiro", "Kiki Lima"]
CATEGORIES = ["Todas", "Livros", "Catálogos", "Serigrafias", "Gravuras", "Pinturas", "Guaches e aguarelas", "Esculturas", "Desenhos", "Fotografias", "Posters e cartazes"]
PATTERNS = {"Livros": r"livro|book|monografia", "Catálogos": r"catálogo|catalog", "Serigrafias": r"serigrafia|serigraph|screenprint|silkscreen", "Gravuras": r"gravura|etching|lithograph|litografia|xilogravura", "Pinturas": r"pintura|painting|óleo|oil on|acrílico|acrylic", "Guaches e aguarelas": r"guache|gouache|aguarela|watercolou?r", "Esculturas": r"escultura|sculpture|cerâmica|ceramic", "Desenhos": r"desenho|drawing|lápis|grafite", "Fotografias": r"fotografia|photograph", "Posters e cartazes": r"poster|cartaz|affiche"}
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"

def get(url, timeout=12):
    with _HTTP_LOCK:
        cached = _HTTP_CACHE.get(url)
    if cached is not None:
        return cached
    headers = {
        "User-Agent": UA,
        "Accept": "application/json,text/html,*/*",
        "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
    }
    # O Referer da P55 só é enviado à própria P55 (antes ia para todos os sites).
    if "p55.art" in urlparse(url).netloc:
        headers["Referer"] = "https://www.p55.art/"
    req = Request(url, headers=headers)
    started = time.time()
    try:
        data = response = None
        last_ssl_error = None
        for ctx_name, ctx in _SSL_CONTEXTS:
            try:
                with urlopen(req, timeout=timeout, context=ctx) as response:
                    data = response.read()
                break
            except Exception as exc:
                reason = getattr(exc, "reason", exc)
                if isinstance(reason, ssl.SSLCertVerificationError) or "CERTIFICATE_VERIFY_FAILED" in str(exc):
                    last_ssl_error = exc
                    LOG.warning("Certificado recusado (%s) em %s: %s", ctx_name, url, exc)
                    continue
                raise
        if data is None:
            raise RuntimeError(f"Certificado de segurança recusado por {urlparse(url).netloc}: {last_ssl_error}")
        LOG.info("GET %s -> %s (%d bytes, %.1fs)", url, getattr(response, "status", "?"), len(data), time.time() - started)
        with _HTTP_LOCK:
            if len(_HTTP_CACHE) > _HTTP_CACHE_MAX:
                _HTTP_CACHE.clear()
            _HTTP_CACHE[url] = data
        return data
    except HTTPError as exc:
        LOG.warning("GET %s -> HTTP %s", url, exc.code)
        # O erro pertence ao URL consultado, nunca deve ser atribuído à P55.art
        # quando a chamada veio do Bing, DuckDuckGo, Brave ou outra fonte.
        raise RuntimeError(f"HTTP {exc.code} em {urlparse(url).netloc}: {exc.reason}") from exc
    except Exception as exc:
        LOG.warning("GET %s -> %s: %s", url, type(exc).__name__, exc)
        raise


def product_details(product, artist):
    title = html.unescape(product.get("title", ""))
    description = html.unescape(re.sub(r"<[^>]+>", " ", product.get("body_html") or ""))
    tags = " ".join(product.get("tags", []) if isinstance(product.get("tags"), list) else [])
    # A P55 pode indicar na descrição que uma edição está esgotada junto do
    # editor, embora o exemplar anunciado pelo vendedor continue disponível.
    # Para produtos Shopify, a disponibilidade do anúncio é determinada pelas
    # variantes, não por palavras soltas no texto editorial.
    variants = [v for v in product.get("variants", []) if v.get("available")]
    if not variants:
        return None
    prices = []
    for variant in variants:
        try: prices.append(float(variant["price"]))
        except (KeyError, TypeError, ValueError): pass
    price = min(prices) if prices else None
    images = product.get("images") or []
    handle = product.get("handle", "")
    image_url = ""
    if images:
        first_image = images[0]
        image_url = first_image.get("src", "") if isinstance(first_image, dict) else str(first_image)
    return {"artist": artist, "title": title, "price": price,
        "price_text": ("€" + format(price, ",.2f").replace(",", "X").replace(".", ",").replace("X", ".")) if price is not None else "Preço não indicado",
        "url": "https://www.p55.art/products/" + handle, "image": image_url,
        "description": re.sub(r"\s+", " ", description).strip()[:320], "source": "P55.art",
        "availability": "Variante disponível no catálogo", "shipping": "Confirmar portes e envio para Portugal no checkout"}

def _p55_collection_handle(name):
    """Converte o nome do artista no identificador habitual de colecção Shopify."""
    value = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^A-Za-z0-9]+", "-", value.casefold()).strip("-")
    return value


class _P55ProductLinkParser(HTMLParser):
    """Extrai identificadores de produtos do HTML público de uma colecção."""
    def __init__(self):
        super().__init__()
        self.links = set()

    def _add(self, value):
        if not value:
            return
        value = html.unescape(str(value)).replace("\\/", "/")
        for match in re.finditer(r"(?:https?://www\.p55\.art)?/products/([^\s\"'<>?#/\\]+)", value):
            self.links.add(match.group(1))

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for key in ("href", "content", "data-href", "data-url", "data-product-url"):
            self._add(attrs.get(key, ""))


def _p55_collection_html_products(handle, max_pages=20):
    """Percorre toda a colecção, sem assumir um mínimo de cartões por página."""
    handles = []
    seen = set()
    for page_number in range(1, max_pages + 1):
        url = f"https://www.p55.art/collections/{quote(handle)}?page={page_number}"
        page = get(url).decode("utf-8", "replace")
        parser = _P55ProductLinkParser()
        parser.feed(page)
        # Alguns temas Shopify guardam os endereços escapados em JSON/JavaScript.
        parser._add(page)
        new_handles = sorted(h for h in parser.links if h not in seen)
        if not new_handles:
            break
        handles.extend(new_handles)
        seen.update(new_handles)

    products = []
    for product_handle in handles:
        product = None
        try:
            payload = json.loads(get(f"https://www.p55.art/products/{quote(product_handle, safe='%')}.js").decode("utf-8", "replace"))
            if isinstance(payload, dict) and payload.get("handle"):
                product = payload
        except Exception:
            pass

        if product is None:
            try:
                raw = get(f"https://www.p55.art/products/{quote(product_handle, safe='%')}").decode("utf-8", "replace")
                blocks = re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', raw, re.I | re.S)
                for block in blocks:
                    try:
                        data = json.loads(html.unescape(block))
                    except Exception:
                        continue
                    candidates = data if isinstance(data, list) else [data]
                    for candidate in candidates:
                        if isinstance(candidate, dict) and candidate.get("@type") == "Product":
                            offers = candidate.get("offers") or {}
                            if isinstance(offers, list):
                                offers = offers[0] if offers else {}
                            image = candidate.get("image") or []
                            if isinstance(image, str):
                                image = [image]
                            price = offers.get("price") if isinstance(offers, dict) else None
                            availability = str(offers.get("availability", "")) if isinstance(offers, dict) else ""
                            product = {
                                "handle": product_handle, "title": candidate.get("name", ""),
                                "body_html": candidate.get("description", ""),
                                "images": [{"src": image[0]}] if image else [],
                                "variants": [{"available": "InStock" in availability, "price": str(price or "")}],
                            }
                            break
                    if product:
                        break
            except Exception:
                pass
        if product:
            products.append(product)
    return products

def _p55_collection_products(handle, max_pages=8):
    """Obtém produtos de uma colecção P55 através do endpoint público Shopify."""
    products = {}
    for page_number in range(1, max_pages + 1):
        url = (
            f"https://www.p55.art/collections/{quote(handle)}/products.json"
            f"?limit=250&page={page_number}"
        )
        payload = json.loads(get(url).decode("utf-8", "replace"))
        page_products = payload.get("products", [])
        if not isinstance(page_products, list) or not page_products:
            break
        for product in page_products:
            key = product.get("id") or product.get("handle") or product.get("title")
            products[key] = product
        if len(page_products) < 250:
            break
    return list(products.values())


def search_artist(artist, category, limit):
    """
    Pesquisa primeiro a colecção completa do artista na P55 (Shopify products.json).
    O Predictive Search é apenas fallback, pois limita a amostra e não representa
    necessariamente todo o catálogo disponível.
    """
    from scout_engine.normalization import ALIASES

    query_names = ALIASES.get(artist, [artist])
    products_by_key = {}
    collection_errors = []

    # A P55 publica colecções por artista. A API de colecção devolve produtos
    # estruturados e permite obter mais do que os 10/50 resultados do autocomplete.
    handles = list(dict.fromkeys(_p55_collection_handle(name) for name in query_names if name))
    for handle in handles:
        if not handle:
            continue
        try:
            collection_products = _p55_collection_products(handle)
            # O endpoint products.json nem sempre está disponível na loja.
            # Nesse caso, recorrer ao HTML público da colecção e aos endpoints
            # públicos individuais .js, sem perder a pesquisa estruturada antiga.
            if not collection_products:
                collection_products = _p55_collection_html_products(handle)
            for product in collection_products:
                key = product.get("id") or product.get("handle") or product.get("title")
                products_by_key[key] = product
        except Exception as exc:
            collection_errors.append(f"{handle}: {type(exc).__name__}: {exc}")
            try:
                for product in _p55_collection_html_products(handle):
                    key = product.get("id") or product.get("handle") or product.get("title")
                    products_by_key[key] = product
            except Exception as html_exc:
                collection_errors.append(f"{handle} HTML: {type(html_exc).__name__}: {html_exc}")

    # Fallback: mantém o autocomplete para nomes cujo identificador de colecção
    # não siga a convenção previsível ou quando o endpoint de colecção falha.
    suggest_errors = []
    suggest_ok = 0
    if not products_by_key:
        for query_name in query_names:
            url = (
                "https://www.p55.art/search/suggest.json?q=" + quote(query_name) +
                "&resources[type]=product&resources[limit]=50" +
                "&resources[options][unavailable_products]=last"
            )
            try:
                data = json.loads(get(url).decode("utf-8", "replace"))
                suggest_ok += 1
                for product in data.get("resources", {}).get("results", {}).get("products", []):
                    key = product.get("handle") or product.get("url") or product.get("title")
                    products_by_key[key] = product
            except Exception as exc:
                suggest_errors.append(f"{type(exc).__name__}: {exc}")
                continue
        # Correcção 0.4.1: se nenhum pedido à P55 resultou, é FALHA (antes
        # aparecia como "0 resultados, 0 falhas").
        if not products_by_key and suggest_ok == 0 and (collection_errors or suggest_errors):
            raise RuntimeError("P55.art inacessível: " + (collection_errors + suggest_errors)[0][:400])

    results = []
    for product in products_by_key.values():
        # products.json contém variantes e estado real de disponibilidade.
        if product.get("variants") is not None:
            item = product_details(product, artist)
            if not item:
                continue
            combined = " ".join([
                str(product.get("title", "")),
                str(product.get("body_html", "")),
                " ".join(product.get("tags", []) if isinstance(product.get("tags"), list) else [])
            ])
        else:
            # Formato devolvido pelo endpoint Predictive Search.
            title = html.unescape(product.get("title", "")).strip()
            description = html.unescape(re.sub(
                r"<[^>]+>", " ",
                product.get("body", "") or product.get("description", "") or ""
            ))
            tags = " ".join(product.get("tags", []) if isinstance(product.get("tags"), list) else [])
            combined = title + " " + description + " " + tags
            # O texto descritivo pode mencionar uma edição esgotada no editor,
            # sem que o exemplar anunciado na P55 esteja esgotado. A flag
            # `available` é a fonte de verdade quando o Predictive Search a envia.
            if product.get("available") is False:
                continue
            raw_price = product.get("price")
            try:
                price = float(str(raw_price).replace(",", ".")) if raw_price not in (None, "") else None
            except (TypeError, ValueError):
                price = None
            product_url = product.get("url") or ""
            if product_url.startswith("/"):
                product_url = "https://www.p55.art" + product_url
            if not product_url and product.get("handle"):
                product_url = "https://www.p55.art/products/" + product["handle"]
            image = product.get("featured_image") or product.get("image") or ""
            if isinstance(image, dict):
                image = image.get("url") or image.get("src") or ""
            if image.startswith("//"):
                image = "https:" + image
            item = {
                "artist": artist, "title": title, "price": price,
                "price_text": ("€" + format(price, ",.2f").replace(",", "X").replace(".", ",").replace("X", ".")) if price is not None else "Preço não indicado",
                "url": product_url, "image": image,
                "description": re.sub(r"\s+", " ", description).strip()[:320],
                "source": "P55.art",
                "availability": "Disponível no catálogo, segundo a pesquisa da loja" if product.get("available") is True else "Disponibilidade por confirmar na página do produto",
                "shipping": "Confirmar portes e envio para Portugal no checkout"
            }

        if category != "Todas" and not re.search(PATTERNS.get(category, r"."), combined, re.I):
            continue
        if item.get("url") and item["url"] not in {r["url"] for r in results}:
            results.append(item)

    results.sort(key=lambda item: (item["price"] is None, item["price"] if item["price"] is not None else 1e20))
    return results[:limit]

def slug_artist(artist):
    value = unicodedata.normalize("NFKD", artist)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value

def search_sao_mamede(artist, category, limit):
    """Galeria São Mamede: página pública do artista + ficha de cada obra.

    Correcção 0.4.0: as ligações das obras são /listagem/obras-de-arte/<slug>
    e o texto da ligação NÃO repete o nome do artista; a versão anterior exigia
    o nome no texto e por isso nunca encontrava obras."""
    return adapters.search_sao_mamede(artist, category, limit, get, PATTERNS)


# Conectores directos para alfarrabistas. Não dependem do Bing.
BOOKSHOP_SOURCES = {
    "Alfarrabista Manuel Ferreira": "https://livrariaferreira.pt",
    "Livraria Alfarrabista Liliana Queiroz": "https://www.livrariaalfarrabista.com",
    "Livraria Sá da Costa": "https://www.sadacosta.com",
}

class _HTMLNode:
    def __init__(self, tag="root", attrs=None, parent=None):
        self.tag = tag
        self.attrs = dict(attrs or [])
        self.parent = parent
        self.children = []
        self.parts = []

    def text(self):
        return " ".join(self.parts + [c.text() for c in self.children]).strip()

    def descendants(self):
        for child in self.children:
            yield child
            yield from child.descendants()


class _TreeParser(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _HTMLNode()
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = _HTMLNode(tag, attrs, self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(_HTMLNode(tag, attrs, self.stack[-1]))

    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        if data and data.strip():
            self.stack[-1].parts.append(data.strip())


class _CardParser:
    """Extrai cartões sem regex de HTML aninhado, que truncava divs internas."""
    CARD_HINTS = ("product", "produto", "livro", "resultado", "listing", "item", "card")

    @staticmethod
    def cards(raw, base, artist):
        parser = _TreeParser()
        parser.feed(raw)
        fold = lambda x: "".join(ch for ch in unicodedata.normalize("NFKD", x.casefold()) if not unicodedata.combining(ch))
        artist_key = fold(artist)
        nodes = list(parser.root.descendants())
        candidates = []
        for node in nodes:
            classes = node.attrs.get("class", "").casefold().split()
            if node.tag == "article" or any(any(h in c for h in _CardParser.CARD_HINTS) for c in classes):
                candidates.append(node)
        # Prefer cartões mais pequenos para não transformar a página inteira num único resultado.
        candidate_ids = {id(n) for n in candidates}
        out, seen = [], set()
        for node in candidates:
            plain = re.sub(r"\s+", " ", html.unescape(node.text())).strip()
            if not plain or artist_key not in fold(plain):
                continue
            descendants = list(node.descendants())
            link_node = next((n for n in descendants if n.tag == "a" and n.attrs.get("href")), None)
            if not link_node:
                continue
            href = html.unescape(link_node.attrs.get("href", "")).strip()
            from urllib.parse import urljoin
            href = urljoin(base.rstrip("/") + "/", href)
            parsed, base_parsed = urlparse(href), urlparse(base)
            if parsed.scheme not in ("http", "https") or not (parsed.netloc == base_parsed.netloc or parsed.netloc.endswith("." + base_parsed.netloc)):
                continue
            if href in seen:
                continue
            seen.add(href)
            if re.search(r"\b(vendido|esgotado|indispon[ií]vel|out of stock|sold)\b", plain, re.I):
                continue
            title_node = next((n for n in descendants if n.tag in ("h1", "h2", "h3", "h4")), None) or link_node
            title = re.sub(r"\s+", " ", html.unescape(title_node.text())).strip() or plain[:150]
            price_node = next((n for n in descendants if "price" in n.attrs.get("class", "").casefold() or "preco" in n.attrs.get("class", "").casefold()), None)
            price_text = price_node.text() if price_node else plain
            pm = re.search(r"(?:€\s?\d[\d.,]*|\d[\d.,]*\s?€)", price_text)
            price = None
            if pm:
                token = re.sub(r"[^0-9,.]", "", pm.group(0))
                if "," in token and "." in token:
                    token = token.replace(".", "").replace(",", ".")
                elif "," in token:
                    token = token.replace(",", ".")
                try:
                    price = float(token)
                except ValueError:
                    pass
            img_node = next((n for n in descendants if n.tag == "img" and (n.attrs.get("src") or n.attrs.get("data-src"))), None)
            image = urljoin(base.rstrip("/") + "/", (img_node.attrs.get("src") or img_node.attrs.get("data-src"))) if img_node else ""
            out.append({"title": title[:220], "price": price,
                "price_text": ("€" + format(price, ",.2f").replace(",", "X").replace(".", ",").replace("X", ".")) if price is not None else "Preço não indicado",
                "url": href, "image": image, "description": plain[:400]})
        return out

BOOKSHOP_FALLBACK_URLS = {
    "Alfarrabista Manuel Ferreira": ["/?s={q}&post_type=product", "/search/{q}/"],
    "Livraria Sá da Costa": ["/livros?pesquisa={q}", "/livros?search={q}", "/livros?q={q}", "/pesquisa?q={q}"],
    "Livraria Alfarrabista Liliana Queiroz": ["/?tipo=pesq&pesq={q}", "/?tipo=pesq&query={q}", "/?tipo=pesq&pesquisa={q}",
                                               "/?tipo=pesq&txt={q}", "/?tipo=pesq&q={q}"],
}


def search_bookshop(artist, category, source, limit):
    """Livrarias/alfarrabistas com conector directo.

    Correcção 0.4.0: descobre o formulário de pesquisa real na página inicial
    (Liliana Queiroz respondia "Falta a pesquisa" ao parâmetro antigo; Sá da
    Costa mudou para /livros). Os cartões sem imagem/preço são completados
    com a ficha individual (og:image, JSON-LD), como na versão FILTRO_LIVROS."""
    base = BOOKSHOP_SOURCES[source]
    q = quote(artist)
    fallback = [base + path.format(q=q) for path in BOOKSHOP_FALLBACK_URLS.get(source, [])]
    return adapters.search_bookshop_auto(artist, category, source, base, get, _CardParser.cards,
                                         PATTERNS, fallback_urls=fallback, limit=limit)


# Fontes recuperadas. As fontes sem conector próprio usam pesquisa multi-motor
# restrita ao domínio e são identificadas como candidatos, nunca como anúncios validados.
SOURCE_DOMAINS = {
    "Galeria São Mamede": "saomamede.com",
    "Galeria 111": "111.pt",
    "Underdogs Gallery": "under-dogs.net",
    "Galerias de Edições Nacionais": "galeriasdeedicoesnacionais.pt",
    "IberLibro": "iberlibro.com",
    "ZVAB": "zvab.com",
    "AbeBooks": "abebooks.com",
    "Artsy Buy Now": "artsy.net",
    "Kleinanzeigen": "kleinanzeigen.de",
    "Wallapop": "wallapop.com",
    "Vinted": "vinted.pt",
    "OLX": "olx.pt",
    "CustoJusto": "custojusto.pt",
    "Homem dos Livros": "homemdoslivros.com",
    "Manuseado": "manuseado.pt",
    "Livraria Trindade": "livrariatrindade.pt",
    "Paraíso do Livro": "paraisodolivro.pt",
    "Livraria Ultramarina": "livrariaultramarina.com",
    "O Bibliognosta": "obibliognosta.pt",
    "Centro Português de Serigrafia": "cps.pt",
    "Art4All": "art4all.pt",
    "Culturas Galeria": "culturas.pt",
    "Clube Rastro": "clubedearte.pt",
    "MundoMolduras": "mundomolduras.com",
    "Galeria CNAP": "galeriadearte.pt",
    "Galeria Sete": "galeriasete.com",
    "A23 Galeria de Arte": "a23.pt",
    "Colectivo Besta": "colectivobesta.com",
    "TWOART Gallery": "twoart.net",
    "In7Artes": "in7artes.com",
    "Galeria Nicolau Nasoni": "galerianicolaunasoni.pt",
    "Obras de Arte": "obrasdearte.pt",
    "ArtMajeur Portugal": "artmajeur.com",
    "Livraria Moreira da Costa": "livrariamoreiradacosta.com",
    "Livraria Castro e Silva": "castroesilva.com",
    "Livraria Miguel de Carvalho": "livrariamigueldecarvalho.com",
    "Alfarrabista Duque": "alfarrabistaduque.pt",
    'Trade Stories': 'tradestories.pt',
    'Cash Converters': 'cashconverters.pt',
    'CeX Portugal': 'webuy.com',
    'Micolet': 'micolet.pt',
    'eBay': 'ebay.com',
    'Milanuncios': 'milanuncios.com',
    'Leboncoin': 'leboncoin.fr',
    'Marktplaats': 'marktplaats.nl',
    'Subito': 'subito.it',
    'FINN.no': 'finn.no',
    'DBA': 'dba.dk',
    'Delcampe': 'delcampe.net',
    'Todocoleccion': 'todocoleccion.net',
    'Selency': 'selency.fr',
    'Pamono': 'pamono.eu',
    '1stDibs': '1stdibs.com',
    'Booklooker': 'booklooker.de',
    'Medimops': 'medimops.de',
    'Discogs': 'discogs.com',
    'Reverb': 'reverb.com',
    'Vestiaire Collective': 'vestiairecollective.com',
    'Depop': 'depop.com',
    'Sellpy': 'sellpy.com',
    'Rakuten France': 'fr.shopping.rakuten.com',
    'ParuVendu': 'paruvendu.fr',
    '2dehands': '2dehands.be',
    'Allegro': 'allegro.pl',
    'Shpock': 'shpock.com',
    'Back Market': 'backmarket.pt',
}


# Organização funcional das fontes: arte, livros e classificados úteis para ambos.
ART_SOURCES = [
    "P55.art", "Galeria São Mamede", "Underdogs Gallery", "Centro Português de Serigrafia",
    "Art4All", "Culturas Galeria", "TWOART Gallery", "Galeria 111", "In7Artes",
    "Artsy Buy Now", "Obras de Arte", "ArtMajeur Portugal", "Selency", "Pamono", "1stDibs",
]
# Fontes retiradas das pesquisas em 22-11-2026: o endereço registado não abriu
# no navegador do utilizador. Ficam aqui para não se perder a informação;
# voltam à lista quando o endereço correcto for confirmado.
DISABLED_SOURCES = {
    "Galerias de Edições Nacionais": "galeriasdeedicoesnacionais.pt não abre",
    "Clube Rastro": "clubedearte.pt não abre",
    "MundoMolduras": "mundomolduras.com não abre",
    "Galeria CNAP": "galeriadearte.pt não abre",
    "Galeria Sete": "galeriasete.com não abre",
    "A23 Galeria de Arte": "a23.pt não abre",
    "Colectivo Besta": "colectivobesta.com não abre",
    "Galeria Nicolau Nasoni": "galerianicolaunasoni.pt não abre",
}
BOOK_SOURCES = [
    "Alfarrabista Manuel Ferreira", "Livraria Alfarrabista Liliana Queiroz",
    "Livraria Sá da Costa", "Homem dos Livros", "Manuseado", "Livraria Trindade",
    "Paraíso do Livro", "Livraria Ultramarina", "O Bibliognosta",
    "Livraria Moreira da Costa", "Livraria Castro e Silva",
    "Livraria Miguel de Carvalho", "Alfarrabista Duque", "IberLibro", "ZVAB",
    "AbeBooks", "Trade Stories", "Booklooker", "Medimops",
]
SHARED_USED_SOURCES = [
    "OLX", "CustoJusto", "Wallapop", "Vinted", "Kleinanzeigen", "eBay",
    "Milanuncios", "Leboncoin", "Marktplaats", "Subito", "FINN.no", "DBA",
    "Delcampe", "Todocoleccion", "2dehands", "Allegro", "Shpock",
]
OTHER_USED_SOURCES = [
    "Cash Converters", "CeX Portugal", "Micolet", "Discogs", "Reverb",
    "Vestiaire Collective", "Depop", "Sellpy", "Rakuten France",
    "ParuVendu", "Back Market",
]
SOURCE_GROUPS = {
    "Fontes de arte": ART_SOURCES,
    "Fontes de livros": BOOK_SOURCES,
    "Usados, arte e livros": SHARED_USED_SOURCES,
    "Outros usados": OTHER_USED_SOURCES,
}

# Motor de pesquisa: combina Bing, DuckDuckGo e Brave. Google é deliberadamente
# excluído da recolha automática por apresentar protecções anti-bot frequentes.
def _engine_results_enhanced(engine, query, domain, timeout=14):
    """Consulta um motor e extrai ligações para o domínio pretendido.

    Primeiro tenta os marcadores conhecidos do motor. Se mudarem, usa uma
    segunda passagem baseada em âncoras HTML, sem aceitar links para outros domínios.
    """
    from urllib.parse import quote_plus, parse_qs, urlsplit, unquote
    if engine == "Bing":
        url = "https://www.bing.com/search?q=" + quote_plus(query) + "&count=30"
    elif engine == "DuckDuckGo":
        url = "https://html.duckduckgo.com/html/?q=" + quote_plus(query)
    else:
        url = "https://search.brave.com/search?q=" + quote_plus(query) + "&source=web"
    raw = get(url, timeout=timeout).decode("utf-8", "replace")
    if re.search(r"captcha|unusual traffic|verify you are human|access denied", raw, re.I):
        raise RuntimeError(f"{engine} apresentou uma página de bloqueio")
    found=[]

    def add(link, title, snippet=""):
        link=html.unescape(link or "").strip()
        title=html.unescape(re.sub(r"<[^>]+>", " ", title or ""))
        snippet=html.unescape(re.sub(r"<[^>]+>", " ", snippet or ""))
        link=link.replace("&amp;", "&")
        if engine == "DuckDuckGo" and "duckduckgo.com/l/?" in link:
            target=parse_qs(urlsplit(link).query).get("uddg", [])
            if target: link=unquote(target[0])
        if link.startswith("//"): link="https:"+link
        host=re.sub(r"^www\.", "", urlsplit(link).netloc.lower())
        if (host == domain or host.endswith("."+domain)) and title.strip():
            found.append((re.sub(r"\s+"," ",title).strip(),link,re.sub(r"\s+"," ",snippet).strip()))

    # Extracção específica, quando os marcadores antigos ainda existem.
    if engine == "Bing":
        for block in re.findall(r'<li\b[^>]*class=["\'][^"\']*\bb_algo\b[^"\']*["\'][^>]*>.*?</li>',raw,re.I|re.S):
            m=re.search(r'<h2[^>]*>\s*<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',block,re.I|re.S)
            if m: add(m.group(1),m.group(2),block)
    elif engine == "DuckDuckGo":
        for m in re.finditer(r'<a\b[^>]*class=["\'][^"\']*result__a[^"\']*["\'][^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',raw,re.I|re.S):
            add(m.group(1),m.group(2),raw[m.end():m.end()+1200])
    else:
        for block in re.findall(r'<div\b[^>]*class=["\'][^"\']*snippet[^"\']*["\'][^>]*>.*?</div>',raw,re.I|re.S):
            m=re.search(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',block,re.I|re.S)
            if m: add(m.group(1),m.group(2),block)

    # Fallback estrutural: percorre todas as âncoras e filtra estritamente o domínio.
    if not found:
        for m in re.finditer(r'<a\b([^>]*)>(.*?)</a>',raw,re.I|re.S):
            attrs=m.group(1)
            hm=re.search(r'\bhref\s*=\s*(["\'])(.*?)\1',attrs,re.I|re.S)
            if not hm: continue
            href=hm.group(2)
            inner=m.group(2)
            title=re.sub(r"<[^>]+>"," ",inner)
            if not re.sub(r"\s+","",title): continue
            context=raw[max(0,m.start()-500):min(len(raw),m.end()+900)]
            add(href,title,context)
    # Deduplicar por URL, preservando a primeira ocorrência.
    clean=[]; seen=set()
    for title,link,snippet in found:
        key=link.split("#",1)[0].rstrip("/").lower()
        if key in seen: continue
        seen.add(key); clean.append((title,link,snippet))
    if not clean:
        # Só aceitar zero resultados quando a resposta contém indicadores claros
        # de uma página de pesquisa válida sem correspondências. Caso contrário,
        # reportar formato desconhecido em vez de declarar sucesso falso.
        no_results = re.search(r"no results|did not match any results|nenhum resultado|não foram encontrados resultados|no web results", raw, re.I)
        known_layout = (engine == "Bing" and ("b_algo" in raw or "b_results" in raw)) or (engine == "DuckDuckGo" and ("result__" in raw or "no-results" in raw)) or (engine == "Brave" and ("snippet" in raw or "search-results" in raw))
        # Uma resposta HTML que contém âncoras mas apenas ligações fora do domínio
        # é uma pesquisa válida com zero correspondências para esta fonte.
        has_anchor_response = bool(re.search(r"<a\b", raw, re.I))
        if not no_results and not known_layout and not has_anchor_response:
            raise RuntimeError(f"{engine} respondeu, mas o formato da página não foi reconhecido")
    return clean



def _engine_results_legacy(engine, query, domain, timeout=14):
    from urllib.parse import quote_plus, urljoin
    if engine == "Bing":
        url = "https://www.bing.com/search?q=" + quote_plus(query) + "&count=30"
    elif engine == "DuckDuckGo":
        url = "https://html.duckduckgo.com/html/?q=" + quote_plus(query)
    else:
        url = "https://search.brave.com/search?q=" + quote_plus(query) + "&source=web"
    raw = get(url, timeout=timeout).decode("utf-8", "replace")
    found=[]
    if engine == "Bing":
        blocks = re.findall(r'<li class="b_algo".*?</li>', raw, re.I|re.S)
        for block in blocks:
            m=re.search(r'<h2[^>]*>\s*<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',block,re.I|re.S)
            if not m: continue
            link=html.unescape(m.group(1)); title=html.unescape(re.sub(r'<[^>]+>',' ',m.group(2)))
            sm=re.search(r'<p[^>]*>(.*?)</p>',block,re.I|re.S)
            snippet=html.unescape(re.sub(r'<[^>]+>',' ',sm.group(1))) if sm else ''
            found.append((title.strip(),link,re.sub(r'\s+',' ',snippet).strip()))
    elif engine == "DuckDuckGo":
        for m in re.finditer(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',raw,re.I|re.S):
            link=html.unescape(m.group(1)); title=html.unescape(re.sub(r'<[^>]+>',' ',m.group(2)))
            snippet=''
            block=raw[m.end():m.end()+1800]
            sm=re.search(r'class="result__snippet"[^>]*>(.*?)</(?:a|td|div)',block,re.I|re.S)
            if sm: snippet=html.unescape(re.sub(r'<[^>]+>',' ',sm.group(1)))
            found.append((title.strip(),link,re.sub(r'\s+',' ',snippet).strip()))
    else:
        blocks=re.findall(r'<div[^>]+class="[^\"]*snippet[^\"]*".*?</div>\s*</div>',raw,re.I|re.S)
        for block in blocks:
            m=re.search(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',block,re.I|re.S)
            if not m: continue
            link=html.unescape(m.group(1)); title=html.unescape(re.sub(r'<[^>]+>',' ',m.group(2)))
            snippet=html.unescape(re.sub(r'<[^>]+>',' ',block))
            found.append((title.strip(),link,re.sub(r'\s+',' ',snippet).strip()))
    clean=[]
    for title,link,snippet in found:
        host=re.sub(r'^www\.','',urlparse(link).netloc.lower())
        if host != domain and not host.endswith('.'+domain): continue
        if not title or not link.startswith('http'): continue
        clean.append((title,link,snippet))
    return clean



def _engine_results(engine, query, domain, timeout=14):
    """Prioriza o extractor original, mantendo o extractor melhorado como fallback."""
    legacy_error = None
    try:
        rows = _engine_results_legacy(engine, query, domain, timeout)
        if rows:
            return rows
    except Exception as exc:
        legacy_error = exc
    try:
        rows = _engine_results_enhanced(engine, query, domain, timeout)
        if rows:
            return rows
        if legacy_error:
            raise RuntimeError(f"Extractor original: {legacy_error}; extractor alternativo sem resultados")
        return rows
    except Exception as enhanced_error:
        if legacy_error:
            raise RuntimeError(f"Extractor original: {legacy_error}; extractor alternativo: {enhanced_error}") from enhanced_error
        raise


def search_external(artist, category, source, limit):
    domain = SOURCE_DOMAINS[source]
    cat_term = "" if category == "Todas" else category
    from scout_engine.normalization import ALIASES
    variants = ALIASES.get(artist, [artist])
    artist_query = " OR ".join('"'+v.replace('"', '')+'"' for v in variants)
    category_terms={"Livros":"livro OR book OR monografia", "Catálogos":"catálogo OR catalogo OR catalogue", "Serigrafias":"serigrafia OR serigraph OR screenprint", "Gravuras":"gravura OR gravure OR lithograph OR litografia", "Pinturas":"pintura OR painting OR quadro", "Esculturas":"escultura OR sculpture", "Desenhos":"desenho OR drawing", "Fotografias":"fotografia OR photograph"}
    extra=category_terms.get(category, "obra OR arte OR livro OR catálogo OR serigrafia OR gravura")
    if source == "Artsy Buy Now": extra += ' "Buy Now"'
    query=f'site:{domain} ({artist_query}) ({extra})'
    results=[]; errors=[]; seen=set(); engines_ok=0
    for engine in ("Bing","DuckDuckGo","Brave"):
        try:
            engine_rows = _engine_results(engine,query,domain)
            engines_ok += 1
            for title,link,snippet in engine_rows:
                key=link.split('?')[0].rstrip('/').lower()
                if key in seen: continue
                seen.add(key)
                combined=title+' '+snippet
                if re.search(r'\b(leil[aã]o|auction|licita[cç][aã]o|bidding|vendid[oa]s?|esgotad[oa]s?|sold|out of stock)\b',combined,re.I): continue
                # Aceitar variantes sem acentos e capitalização.
                fold=lambda x: ''.join(ch for ch in unicodedata.normalize('NFKD',x.casefold()) if not unicodedata.combining(ch))
                if artist_match_score(artist, combined) < 82: continue
                pm=re.search(r'(?:€\s?\d[\d.,]*|\d[\d.,]*\s?€)',title+' '+snippet)
                price=None
                if pm:
                    token=re.sub(r'[^0-9,.]','',pm.group(0))
                    if ',' in token and '.' in token: token=token.replace('.','').replace(',','.')
                    elif ',' in token: token=token.replace(',','.')
                    try: price=float(token)
                    except ValueError: pass
                results.append({"artist":artist,"title":title[:220],"price":price,
                    "price_text":("€"+format(price,',.2f').replace(',', 'X').replace('.',',').replace('X','.')) if price is not None else "Preço não indicado",
                    "url":link,"image":"","description":snippet[:350],"source":source,
                    "availability":"Resultado de motor de pesquisa; confirmar disponibilidade na página original",
                    "shipping":"Envio para Portugal por confirmar","search_engine":engine})
                if len(results)>=limit: break
            if len(results)>=limit: break
        except Exception as exc:
            errors.append(engine+': '+type(exc).__name__+': '+str(exc))
    if not results and engines_ok == 0:
        detail='; '.join(errors) if errors else 'Todos os motores falharam sem devolver resposta.'
        raise RuntimeError('Motores de pesquisa indisponíveis para esta fonte: '+detail)
    # Se pelo menos um motor respondeu correctamente, zero resultados significa
    # apenas que não encontrou correspondências, não que a fonte esteja avariada.
    return results[:limit]

DIRECT_ART = {
    "Underdogs Gallery": lambda a, c, l: adapters.search_shopify_store(a, c, l, get, PATTERNS, "https://www.under-dogs.net", "Underdogs Gallery"),
    "TWOART Gallery": lambda a, c, l: adapters.search_woocommerce_store(a, c, l, get, PATTERNS, "https://twoart.net", "TWOART Gallery"),
    "Centro Português de Serigrafia": lambda a, c, l: adapters.search_cps(a, c, l, get, PATTERNS),
    "Art4All": lambda a, c, l: adapters.search_art4all(a, c, l, get, PATTERNS),
    "Culturas Galeria": lambda a, c, l: adapters.search_culturas(a, c, l, get, PATTERNS),
    "Galeria 111": lambda a, c, l: adapters.search_wordpress_pages(a, c, l, get, PATTERNS, "https://111.pt", "Galeria 111"),
    "In7Artes": lambda a, c, l: adapters.search_wordpress_pages(a, c, l, get, PATTERNS, "https://in7artes.com", "In7Artes"),
}

DIRECT_USED = {
    "OLX": lambda a, c, l: adapters.search_olx(a, c, l, get, PATTERNS),
    "CustoJusto": lambda a, c, l: adapters.search_custojusto(a, c, l, get, PATTERNS),
}


def source_method(source):
    """Como cada fonte é consultada (usado na interface e no diagnóstico)."""
    if source == "P55.art":
        return "directo (catálogo Shopify)"
    if source == "Galeria São Mamede":
        return "directo (página do artista)"
    if source in BOOKSHOP_SOURCES:
        return "directo (pesquisa da livraria)"
    if source in DIRECT_USED or source in DIRECT_ART:
        return "directo (pesquisa pública do site)"
    return "motor de pesquisa (Bing/DuckDuckGo/Brave, site:" + SOURCE_DOMAINS.get(source, "?") + ")"


def search_one(source, name, category, limit, warnings=None):
    """Consulta UMA fonte para UM artista. Excepção = falha técnica."""
    if source == "P55.art":
        # A P55 apresenta catálogos com mais de 50 obras; a paginação da
        # interface apresenta 50 resultados por página.
        return search_artist(name, category, max(limit, 250))
    if source == "Galeria São Mamede":
        return search_sao_mamede(name, category, limit)
    if source in BOOKSHOP_SOURCES:
        return search_bookshop(name, category, source, limit)
    if source in DIRECT_ART:
        return DIRECT_ART[source](name, category, limit)
    if source in DIRECT_USED:
        try:
            return DIRECT_USED[source](name, category, limit)
        except Exception as exc:
            # Motor directo falhou: recorrer ao motor de pesquisa por domínio.
            if warnings is not None:
                warnings.append(f"{source}, {name}: motor directo falhou ({exc}); usado motor de pesquisa")
            LOG.warning("%s directo falhou: %s", source, exc)
            return search_external(name, category, source, limit)
    return search_external(name, category, source, limit)


def canonical_key(raw_url):
    from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
    parts = urlsplit(raw_url or "")
    tracking = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "gclid", "fbclid", "reason", "search_reason"}
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k.casefold() not in tracking])
    return urlunsplit((parts.scheme.casefold(), parts.netloc.casefold().replace("www.", ""), parts.path.rstrip("/"), query, ""))


AREA_LABEL = {"Fontes de arte": "Arte", "Fontes de livros": "Livros", "Usados, arte e livros": "Usados", "Outros usados": "Usados"}


def resolve_sources(selected_source):
    direct_sources = ["P55.art"] + list(BOOKSHOP_SOURCES)
    all_sources = direct_sources + [x for x in SOURCE_DOMAINS if x not in direct_sources]
    if selected_source in SOURCE_GROUPS:
        return [x for x in SOURCE_GROUPS[selected_source] if x in all_sources]
    if selected_source in all_sources:
        return [selected_source]
    # Regra do projecto: não existe pesquisa "todas as áreas de uma vez".
    raise ValueError("Escolha uma área (Arte, Livros ou Usados) ou uma fonte individual: " + str(selected_source))


def do_search(artist, category, limit, task_id=None, selected_source="Fontes de arte"):
    names = [artist] if artist else ARTISTS
    sources = resolve_sources(selected_source)
    area = AREA_LABEL.get(selected_source, "Fonte individual")
    total = len(names) * len(sources); results = []; errors = []; warnings = []; step = 0
    source_counts = {source: 0 for source in sources}
    source_failures = {source: 0 for source in sources}
    collected_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for source in sources:
        for name in names:
            step += 1
            if task_id:
                with TASK_LOCK:
                    if TASKS.get(task_id, {}).get("cancel"):
                        break
                    TASKS[task_id].update({"progress": step-1, "total": total, "current": name+" | "+source, "message": "A consultar "+source+" para "+name})
            try:
                rows = search_one(source, name, category, limit, warnings)
            except Exception as exc:
                errors.append(source+", "+name+": "+type(exc).__name__+": "+str(exc))
                source_failures[source] += 1
                LOG.warning("Falha %s / %s: %s", source, name, exc)
            else:
                for row in rows:
                    row.setdefault("currency", "EUR" if row.get("price") is not None else "")
                    row["category"] = category
                    row["area"] = area
                    row["collected_at"] = collected_at
                    row["method"] = source_method(source)
                    row["validation"] = "por validar pelo utilizador"
                    row["dedup_key"] = hashlib.sha1(canonical_key(row.get("url", "")).encode("utf-8")).hexdigest()[:16]
                results.extend(rows)
                source_counts[source] += len(rows)
            if task_id:
                with TASK_LOCK:
                    TASKS[task_id].update({"progress": step, "current": name+" | "+source, "message": "Concluído: "+source+" | "+name,
                        "partial_results": list(results), "errors": list(errors), "warnings": list(warnings),
                        "empty_sources": [src for src in sources if source_counts[src] == 0 and source_failures[src] == 0]})
            time.sleep(0.35)
        if task_id and TASKS.get(task_id, {}).get("cancel"):
            break
    # Deduplicação por URL canónica, preservando anúncios diferentes da mesma obra.
    # Quando o mesmo URL aparece duas vezes, os campos em falta são completados.
    unique = {}
    for item in results:
        key = item.get("dedup_key")
        if not key:
            continue
        if key not in unique:
            unique[key] = item
        else:
            kept = unique[key]
            for field in ("image", "price", "price_text", "description"):
                if not kept.get(field) or (field == "price_text" and kept.get("price") is None and item.get("price") is not None):
                    if item.get(field):
                        kept[field] = item[field]
    results = list(unique.values())
    results.sort(key=lambda item: (item["price"] is None, item["price"] if item["price"] is not None else 1e20))
    if task_id:
        with TASK_LOCK:
            TASKS[task_id]["warnings"] = warnings
            TASKS[task_id]["source_counts"] = source_counts
            TASKS[task_id]["empty_sources"] = [src for src in sources if source_counts[src] == 0 and source_failures[src] == 0]
    return results, errors

def run_task(task_id, artist, category, limit, selected_source):
    with _HTTP_LOCK:
        _HTTP_CACHE.clear()  # cada pesquisa obtém dados frescos
    LOG.info("Pesquisa iniciada: artista=%r categoria=%r fonte=%r", artist, category, selected_source)
    try:
        results, errors = do_search(artist, category, limit, task_id, selected_source)
        saved = 0
        if _RESULT_STORE is not None:
            try:
                saved = _RESULT_STORE.save_results(results, query_artist=artist, area=AREA_LABEL.get(selected_source, selected_source))
            except Exception as db_exc:
                errors.append("Base de dados local: " + type(db_exc).__name__ + ": " + str(db_exc))
        LOG.info("Pesquisa concluída: %d resultados, %d falhas, %d guardados", len(results), len(errors), saved)
        with TASK_LOCK:
            TASKS[task_id].update({"done": True, "progress": TASKS[task_id]["total"],
                "results": results, "errors": errors, "saved": saved,
                "message": "Pesquisa concluída com limitações" if errors else "Pesquisa concluída"})
    except Exception as exc:
        LOG.exception("Pesquisa terminou com erro")
        with TASK_LOCK:
            TASKS[task_id].update({"done": True, "errors": [str(exc)], "message": "A pesquisa terminou com erro"})


def page():
    source_groups_json = json.dumps(SOURCE_GROUPS, ensure_ascii=False)
    artists_json = json.dumps(ARTISTS, ensure_ascii=False)
    artist_options = "".join("<option value=\"" + html.escape(a, quote=True) + "\">" for a in ARTISTS)
    return r"""<!doctype html>
<html lang="pt"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Caça à Arte Scout</title>
<style>
:root{--bg:#171c24;--panel:#222a35;--panel2:#293341;--gold:#c5a46d;--ink:#f3f0e9;--muted:#aab2bd;--line:#394453;--accent:#d4b47b}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px "Segoe UI",Arial,sans-serif}
header{background:linear-gradient(120deg,#202833,#303947);border-bottom:1px solid #48515e;padding:25px max(18px,calc((100% - 1180px)/2))}
.brand{display:flex;align-items:center;gap:12px;color:var(--gold);font-weight:800;letter-spacing:2px;font-size:13px}
.brand-mark{width:38px;height:38px;border:1px solid var(--gold);border-radius:12px;display:grid;place-items:center;font-size:21px}
header h1{font-size:29px;margin:16px 0 5px;letter-spacing:.5px}header p{color:#c1c8d0;margin:0}
.wrap{max-width:1180px;margin:26px auto;padding:0 16px}.section-title{font-size:17px;margin:0 0 13px}
.area-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:20px}
.area{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:17px;text-align:left;color:var(--ink);cursor:pointer;min-height:148px;transition:.15s}
.area:hover{border-color:var(--gold);transform:translateY(-2px)}.area.active{border:2px solid var(--gold);background:#303744;box-shadow:0 0 0 2px #c5a46d20}
.area .ico{font-size:25px;margin-bottom:10px}.area strong{display:block;font-size:18px;margin-bottom:6px}.area span{font-size:12px;line-height:1.5;color:var(--muted)}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:20px;margin-bottom:18px}
.panel-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:17px}.panel-head h2{margin:0;font-size:19px}.tag{border:1px solid #806c4d;color:#e2c895;padding:5px 9px;border-radius:30px;font-size:11px}
.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}
label{display:block;font-size:12px;color:#cbd1d8;font-weight:700;margin-bottom:7px}
input,select{width:100%;padding:12px 13px;border:1px solid #4a5665;background:#171e27;color:var(--ink);border-radius:8px;font-size:14px;outline:none}
input:focus,select:focus{border-color:var(--gold)}
button.search{margin-top:17px;padding:13px 23px;background:var(--gold);color:#1b2027;border:0;border-radius:8px;font-weight:800;cursor:pointer}
button.search:disabled{opacity:.5;cursor:wait}.hint,.meta{font-size:12px;color:var(--muted);line-height:1.5}.hint{margin:12px 0 0}
#count{display:block;margin:20px 0 8px}.status{padding:12px;background:#2c3541;border:1px solid var(--line);border-radius:8px;margin:12px 0;color:#d7dce2}.error{background:#422e2d;color:#ffd6cf;border-color:#704640}.error ul{margin:8px 0 0;padding-left:22px}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(255px,1fr));gap:15px}
.pager{display:flex;align-items:center;justify-content:center;gap:10px;flex-wrap:wrap;margin:18px 0}
.pager button,.new-search{padding:9px 14px;border:1px solid var(--line);border-radius:8px;background:#293341;color:var(--ink);cursor:pointer}
.pager button:disabled{opacity:.35;cursor:not-allowed}.pager .page-info{color:var(--muted);font-size:13px}
button.secondary{margin-top:17px;padding:13px 18px;background:#293341;color:var(--ink);border:1px solid #536071;border-radius:8px;font-weight:700;cursor:pointer}
.actions{display:flex;gap:10px;align-items:end;flex-wrap:wrap}a.linkbtn{display:inline-block;text-decoration:none;font-size:14px}.noimg{height:120px;display:grid;place-items:center;background:#1b222b;color:var(--muted);font-size:12px}.warn{background:#3b3524;color:#f1e1b5;border-color:#6d6140}.small{font-size:11px;color:#8d96a1}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden;display:flex;flex-direction:column}.card img{width:100%;height:225px;object-fit:contain;background:#1b222b}.inside{padding:14px;display:flex;flex-direction:column;gap:9px;flex:1}.inside h3{margin:0;font-size:16px}.price{font-size:22px;font-weight:bold;color:var(--gold)}.inside a{margin-top:auto;padding-top:10px;border-top:1px solid var(--line);color:#e0c18b;text-decoration:none;font-weight:bold}
@media(max-width:720px){.area-grid{grid-template-columns:1fr}.grid{grid-template-columns:1fr}header h1{font-size:24px}.panel{padding:15px}}
</style></head><body>
<header><div class="brand"><div class="brand-mark">✦</div> CAÇA À ARTE SCOUT</div>
<h1>Centro de Pesquisa <span style="font-size:13px;color:#aab2bd">v0.4.4</span></h1><p>Pesquisa especializada por artista, livros e mercado de usados.</p></header>
<main class="wrap">
<h2 class="section-title">Escolhe uma área de pesquisa</h2>
<div class="area-grid">
<button class="area active" data-area="Fontes de arte" onclick="chooseArea('Fontes de arte')"><div class="ico">▧</div><strong>Arte</strong><span>Galerias, obras originais, pinturas, serigrafias, gravuras, esculturas e fotografia.</span></button>
<button class="area" data-area="Fontes de livros" onclick="chooseArea('Fontes de livros')"><div class="ico">▤</div><strong>Livros</strong><span>Alfarrabistas, monografias, catálogos, primeiras edições e livros raros ou esgotados.</span></button>
<button class="area" data-area="Usados, arte e livros" onclick="chooseArea('Usados, arte e livros')"><div class="ico">⌕</div><strong>Usados</strong><span>Classificados e marketplaces onde podem aparecer obras de arte e livros usados.</span></button>
</div>
<section class="panel">
<div class="panel-head"><h2 id="areaTitle">Pesquisar em Arte</h2><span class="tag" id="areaTag">GALERIAS E MERCADO DE ARTE</span></div>
<div class="grid">
<div><label for="artist">Artista ou termo de pesquisa</label><input id="artist" list="artist-list" placeholder="Artista ou termo livre, deixe vazio para pesquisar todos"><datalist id="artist-list">ARTISTS</datalist></div>
<div><label for="category">Tipo de artigo</label><select id="category"></select></div>
<div><label for="source">Fonte</label><select id="source"></select></div>
</div>
<div class="grid" style="margin-top:14px"><div><label for="limit">Resultados por fonte</label><select id="limit"><option>5</option><option>10</option><option>20</option><option selected>50</option></select></div><div class="actions"><button class="search" id="go" onclick="runSearch()">Pesquisar nesta área</button><button class="secondary" id="newSearch" type="button" onclick="newSearch()">Nova pesquisa</button></div></div>
<div class="actions" style="margin-top:4px"><button class="secondary" type="button" onclick="showHistory()">Histórico guardado</button><a class="secondary linkbtn" href="/api/export?format=csv">Exportar CSV</a><a class="secondary linkbtn" href="/api/export?format=json">Exportar JSON</a></div>
<p class="hint" id="areaHint">A pesquisa consulta apenas fontes de arte. Para pesquisar livros ou usados, selecciona outra área.</p>
</section>
<strong id="count">Ainda sem pesquisa</strong><div id="status"></div><nav id="pagerTop" class="pager" aria-label="Paginação (topo)"></nav><section class="cards" id="results"></section><nav id="pager" class="pager" aria-label="Paginação dos resultados"></nav>
</main>
<script>
const SOURCE_GROUPS=SOURCE_GROUPS_JSON;
const ARTISTS=ARTISTS_JSON;
const CATEGORY_OPTIONS={
 "Fontes de arte":[["Todas","Todas"],["Serigrafias","Serigrafias"],["Gravuras","Gravuras"],["Pinturas","Pinturas"],["Guaches e aguarelas","Guaches e aguarelas"],["Esculturas","Esculturas"],["Desenhos","Desenhos"],["Fotografias","Fotografias"],["Posters e cartazes","Posters e cartazes"]],
 "Fontes de livros":[["Todos os livros e catálogos","Todas"],["Livros","Livros"],["Catálogos","Catálogos"]],
 "Usados, arte e livros":[["Todos os artigos","Todas"],["Obras de arte","Todas"],["Livros usados","Livros"],["Serigrafias","Serigrafias"],["Gravuras","Gravuras"],["Pinturas","Pinturas"],["Catálogos e livros","Livros"]]
};
const META={
 "Fontes de arte":["Pesquisar em Arte","GALERIAS E MERCADO DE ARTE","A pesquisa consulta apenas fontes de arte."],
 "Fontes de livros":["Pesquisar em Livros","ALFARRABISTAS E LIVRARIAS","A pesquisa consulta apenas alfarrabistas e livrarias."],
 "Usados, arte e livros":["Pesquisar em Usados","CLASSIFICADOS E MARKETPLACES","A pesquisa consulta apenas plataformas generalistas de usados, onde podem surgir livros e obras de arte."]
};
let activeArea="Fontes de arte";
function fillSelect(el,items){el.innerHTML=items.map(x=>'<option value="'+esc(x[1])+'">'+esc(x[0])+'</option>').join('')}
function chooseArea(area){
 activeArea=area;document.querySelectorAll('.area').forEach(b=>b.classList.toggle('active',b.dataset.area===area));
 document.getElementById('areaTitle').textContent=META[area][0];document.getElementById('areaTag').textContent=META[area][1];document.getElementById('areaHint').textContent=META[area][2]+' Não são executadas pesquisas nas outras áreas.';
 fillSelect(document.getElementById('category'),CATEGORY_OPTIONS[area]);
 const names=SOURCE_GROUPS[area]||[];
 fillSelect(document.getElementById('source'),[["Todas as fontes desta área",area],...names.map(n=>[n,n])]);
 document.getElementById('count').textContent='Área seleccionada: '+(area==='Fontes de arte'?'Arte':area==='Fontes de livros'?'Livros':'Usados');
 document.getElementById('status').innerHTML='';document.getElementById('results').innerHTML='';document.getElementById('pager').innerHTML='';document.getElementById('pagerTop').innerHTML='';allRows=[];currentPage=1;
}
function esc(s){return String(s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
let allRows=[];
let currentPage=1;
const PAGE_SIZE=50;
let activeTask=null;
function showPage(requestedPage,scroll){
 const totalPages=Math.max(1,Math.ceil(allRows.length/PAGE_SIZE));
 const parsed=Number.parseInt(requestedPage,10);
 if(!Number.isFinite(parsed)) return;
 currentPage=Math.max(1,Math.min(parsed,totalPages));
 const first=(currentPage-1)*PAGE_SIZE;
 document.getElementById('results').innerHTML=renderCards(allRows.slice(first,first+PAGE_SIZE));
 const pager=document.getElementById('pager');
 if(totalPages<=1){pager.innerHTML='';const t=document.getElementById('pagerTop');if(t)t.innerHTML='';return;}
 pager.innerHTML='<button type="button" data-page="1" onclick="showPage(1)" '+(currentPage===1?'disabled':'')+'>Primeira</button>'+
 '<button type="button" data-page="'+(currentPage-1)+'" onclick="showPage('+(currentPage-1)+')" '+(currentPage===1?'disabled':'')+'>Anterior</button>'+
 '<span class="page-info">Página '+currentPage+' de '+totalPages+' · '+allRows.length+' resultados</span>'+
 '<button type="button" data-page="'+(currentPage+1)+'" onclick="showPage('+(currentPage+1)+')" '+(currentPage===totalPages?'disabled':'')+'>Seguinte</button>'+
 '<button type="button" data-page="'+totalPages+'" onclick="showPage('+totalPages+')" '+(currentPage===totalPages?'disabled':'')+'>Última</button>';
 pager.setAttribute('aria-live','polite');
 const top=document.getElementById('pagerTop');if(top)top.innerHTML=pager.innerHTML;
 if(scroll!==false){document.getElementById('count').scrollIntoView({behavior:'smooth',block:'start'});}
}
function newSearch(){
 if(activeTask){fetch('/api/cancel?id='+encodeURIComponent(activeTask));activeTask=null;}
 allRows=[];currentPage=1;
 document.getElementById('results').innerHTML='';
 document.getElementById('pager').innerHTML='';document.getElementById('pagerTop').innerHTML='';
 document.getElementById('status').innerHTML='';
 document.getElementById('count').textContent='Pronto para nova pesquisa';
 document.getElementById('go').disabled=false;
 document.getElementById('go').textContent='Pesquisar nesta área';
 const a=document.getElementById('artist');a.value='';a.focus();
}
async function runSearch(){
 const b=document.getElementById('go');
 if(b.disabled)return;
 activeTask=null;allRows=[];currentPage=1;
 document.getElementById('results').innerHTML='';
 document.getElementById('pager').innerHTML='';document.getElementById('pagerTop').innerHTML='';
 b.disabled=true;b.textContent='A pesquisar…';
 document.getElementById('count').textContent='Pesquisa em curso';
 document.getElementById('status').innerHTML='<div class=status>A iniciar pesquisa apenas na área seleccionada.</div>';
 try{
 let p=new URLSearchParams({artist:document.getElementById('artist').value.trim(),category:document.getElementById('category').value,source:document.getElementById('source').value,limit:document.getElementById('limit').value});
 let r=await fetch('/api/start?'+p,{cache:'no-store'});let j=await r.json();if(!r.ok||!j.task)throw new Error(j.error||'Não foi possível iniciar a pesquisa');
 let task=j.task;activeTask=task;let done=false;
 while(!done && activeTask===task){
  await new Promise(ok=>setTimeout(ok,900));
  let q=await fetch('/api/status?id='+encodeURIComponent(task),{cache:'no-store'});let st=await q.json();
  if(activeTask!==task)break;
  document.getElementById('status').innerHTML='<div class=status>'+esc(st.message||'A pesquisar')+' · '+(st.progress||0)+'/'+(st.total||'?')+' consultas</div>';
  if(st.partial_results&&!st.done){allRows=st.partial_results;document.getElementById('count').textContent=allRows.length+' resultados recolhidos (pesquisa em curso)';showPage(currentPage,false)}
  if(st.done){
   done=true;activeTask=null;allRows=st.results||[];
   document.getElementById('count').textContent=allRows.length+' anúncios encontrados';
   const errorCount=(st.errors||[]).length;
   const queried=Math.max(0,(st.total||0)-errorCount);
   let statusHtml='';
   if(errorCount){
    const heading=queried===0?'Pesquisa sem fontes consultadas com sucesso':'Pesquisa concluída com limitações';
    statusHtml='<div class="status error"><strong>'+heading+' · '+queried+' consultas sem erro · '+errorCount+' falhas</strong><ul>'+st.errors.map(e=>'<li>'+esc(e)+'</li>').join('')+'</ul></div>';
   }else{
    statusHtml='<div class=status>Consulta concluída nas fontes seleccionadas. '+allRows.length+' resultados encontrados.</div>';
   }
   const warns=st.warnings||[];
   if(warns.length){statusHtml+='<div class="status warn"><strong>Avisos ('+warns.length+')</strong><ul>'+warns.map(w=>'<li>'+esc(w)+'</li>').join('')+'</ul></div>';}
   if(st.saved){statusHtml+='<div class=status>'+st.saved+' resultados guardados no histórico local.</div>';}
   const emptySources=st.empty_sources||[];
   if(emptySources.length){
    statusHtml+='<div class=status><strong>Fontes sem resultados:</strong> '+emptySources.map(esc).join(', ')+'. Pretendes excluir alguma destas plataformas das próximas pesquisas? A exclusão só será feita depois da tua confirmação.</div>';
   }
   document.getElementById('status').innerHTML=statusHtml;
   showPage(currentPage,false);
  }
 }
 }catch(e){document.getElementById('status').innerHTML='<div class="status error">Erro: '+esc(e.message)+'</div>'}
 finally{if(activeTask===null){b.disabled=false;b.textContent='Pesquisar nesta área'}}
}
function renderCards(rows){return rows.map(x=>'<article class=card>'+(x.image?'<img loading=lazy referrerpolicy=no-referrer src="'+esc(x.image)+'">':'<div class=noimg>Imagem não disponível na fonte</div>')+'<div class=inside><h3>'+esc(x.title)+'</h3><div class=price>'+esc(x.price_text)+'</div><div class=meta>'+esc(x.artist)+' · '+esc(x.source)+'</div><div class=meta>'+esc(x.availability)+'<br>'+esc(x.shipping)+'</div><div class=meta>'+esc(x.description)+'</div><div class=small>'+esc(x.method||'')+(x.collected_at||x.first_seen?' · recolhido '+esc((x.collected_at||x.first_seen||'').slice(0,10)):'')+(x.published?' · publicado '+esc(String(x.published).slice(0,10)):'')+'</div><a target=_blank rel=noopener href="'+esc(x.url)+'">Abrir anúncio na fonte ↗</a></div></article>').join('')}
async function showHistory(){
 const term=document.getElementById('artist').value.trim();
 document.getElementById('status').innerHTML='<div class=status>A ler o histórico local…</div>';
 try{const r=await fetch('/api/history?q='+encodeURIComponent(term),{cache:'no-store'});const j=await r.json();if(!r.ok)throw new Error(j.error||'Erro');
 allRows=j.results||[];document.getElementById('count').textContent='Histórico: '+allRows.length+' resultados'+(term?' com «'+term+'»':'')+' (total guardado: '+j.total+')';
 document.getElementById('status').innerHTML='<div class=status>Resultados guardados em pesquisas anteriores. Os anúncios podem já não estar activos: confirme na fonte.</div>';showPage(1);}
 catch(e){document.getElementById('status').innerHTML='<div class="status error">Erro: '+esc(e.message)+'</div>'}
}
document.getElementById('artist').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();runSearch()}});
document.getElementById('artist-list').innerHTML=ARTISTS.map(a=>'<option value="'+esc(a)+'">').join('');
chooseArea(activeArea);
</script></body></html>""".replace("SOURCE_GROUPS_JSON", source_groups_json).replace("ARTISTS_JSON", artists_json).replace('<datalist id="artist-list">ARTISTS</datalist>', '<datalist id="artist-list">' + artist_options + '</datalist>')

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            body = page().encode(); self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
        if u.path == "/api/start":
            params = parse_qs(u.query)
            artist = params.get("artist", [""])[0]
            category = params.get("category", ["Todas"])[0]
            selected_source = params.get("source", [""])[0].strip()
            try: limit = max(1, min(50, int(params.get("limit", ["10"])[0])))
            except ValueError: limit = 10
            task_id = uuid.uuid4().hex
            try:
                planned_sources = resolve_sources(selected_source)
            except ValueError as exc:
                return self._json({"error": str(exc)}, 400)
            total = (1 if artist else len(ARTISTS)) * len(planned_sources)
            with TASK_LOCK:
                TASKS[task_id] = {"done": False, "progress": 0, "total": total,
                    "current": "", "message": "A iniciar", "partial_results": [], "errors": []}
            threading.Thread(target=run_task, args=(task_id, artist, category, limit, selected_source), daemon=True).start()
            body = json.dumps({"task": task_id}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
        if u.path == "/api/status":
            task_id = parse_qs(u.query).get("id", [""])[0]
            with TASK_LOCK:
                state = dict(TASKS.get(task_id, {}))
            if not state:
                body = json.dumps({"done": True, "message": "Pesquisa não encontrada"}).encode()
            else:
                body = json.dumps(state, ensure_ascii=False).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
        if u.path == "/api/search":
            params = parse_qs(u.query); artist = params.get("artist", [""])[0]; category = params.get("category", ["Todas"])[0]
            selected_source = params.get("source", ["Fontes de arte"])[0]
            try: limit = max(1, min(50, int(params.get("limit", ["10"])[0])))
            except ValueError: limit = 10
            try:
                results, errors = do_search(artist, category, limit, None, selected_source)
            except ValueError as exc:
                return self._json({"error": str(exc)}, 400)
            body = json.dumps({"results": results, "errors": errors}, ensure_ascii=False).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
        if u.path == "/api/version":
            return self._json({"version": VERSION, "ssl": [n for n, _ in _SSL_CONTEXTS]})
        if u.path == "/api/shutdown":
            self._json({"ok": True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        if u.path == "/api/cancel":
            task_id = parse_qs(u.query).get("id", [""])[0]
            with TASK_LOCK:
                if task_id in TASKS:
                    TASKS[task_id]["cancel"] = True
            return self._json({"ok": True})
        if u.path == "/api/history":
            params = parse_qs(u.query)
            term = params.get("q", [""])[0].strip()
            if _RESULT_STORE is None:
                return self._json({"error": "Base de dados indisponível"}, 500)
            rows = _RESULT_STORE.search(term, 500) if term else _RESULT_STORE.recent(500)
            return self._json({"results": rows, "total": _RESULT_STORE.count()})
        if u.path == "/api/export":
            fmt = parse_qs(u.query).get("format", ["csv"])[0]
            if _RESULT_STORE is None:
                return self._json({"error": "Base de dados indisponível"}, 500)
            rows = _RESULT_STORE.recent(100000)
            stamp = datetime.now().strftime("%Y%m%d_%H%M")
            if fmt == "json":
                body = json.dumps(rows, ensure_ascii=False, indent=1).encode("utf-8")
                ctype, name = "application/json; charset=utf-8", f"caca_arte_resultados_{stamp}.json"
            else:
                import csv, io
                cols = ["first_seen", "last_seen", "area", "source", "artist", "title", "price", "currency", "url", "image",
                        "availability", "listing_id", "published", "location", "dedup_key", "description"]
                buf = io.StringIO()
                w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore", delimiter=";")
                w.writeheader()
                for r in rows:
                    w.writerow(r)
                body = ("\ufeff" + buf.getvalue()).encode("utf-8")
                ctype, name = "text/csv; charset=utf-8", f"caca_arte_resultados_{stamp}.csv"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Disposition", f'attachment; filename="{name}"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body); return
        if u.path == "/api/sources":
            return self._json({area: [{"name": s_, "method": source_method(s_)} for s_ in names]
                               for area, names in SOURCE_GROUPS.items()})
        self.send_error(404)

    def _json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)

def main():
    # Se já houver uma Scout aberta (por exemplo uma versão antiga esquecida
    # noutra janela), pede-lhe para fechar antes de arrancar esta.
    try:
        with urlopen("http://127.0.0.1:8766/api/shutdown", timeout=2):
            pass
        time.sleep(1.5)
    except Exception:
        pass
    try:
        server = ThreadingHTTPServer(("127.0.0.1", 8766), Handler)
    except OSError:
        print("ERRO: a porta 8766 continua ocupada por outra janela da Caça à Arte Scout.")
        print("Feche as outras janelas pretas da Scout e abra de novo.")
        raise
    print("Caça à Arte Scout", VERSION, "- certificados:", ", ".join(n for n, _ in _SSL_CONTEXTS))
    print("Caça à Arte Scout: http://127.0.0.1:8766")
    def open_browser():
        import os, shutil
        candidates = [shutil.which("chrome"), shutil.which("google-chrome"), shutil.which("chrome.exe")]
        for candidate in candidates:
            if candidate:
                try:
                    webbrowser.get('"' + candidate + '" %s').open("http://127.0.0.1:8766")
                    return
                except Exception:
                    pass
        # Caminhos habituais do Chrome em Windows.
        if os.name == "nt":
            for candidate in [os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"), os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"), os.path.expandvars(r"%ProgramW6432%\Google\Chrome\Application\chrome.exe"), os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe")]:
                if os.path.exists(candidate):
                    import subprocess
                    subprocess.Popen([candidate, "http://127.0.0.1:8766"])
                    return
        webbrowser.open("http://127.0.0.1:8766")
    threading.Timer(1, open_browser).start()
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()

if __name__ == "__main__": main()
