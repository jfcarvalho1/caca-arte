# -*- coding: utf-8 -*-
"""Testes offline dos motores corrigidos na 0.4.0 (respostas simuladas).

As estruturas simuladas seguem o que foi observado nos sites reais em
22-11-2026 (São Mamede: ligações /listagem/obras-de-arte/<slug> sem o nome do
artista; Liliana Queiroz: "Falta a pesquisa" com parâmetro errado; OLX:
estado __PRERENDERED_STATE__; CustoJusto: pesquisa muito permissiva).
Não substituem o diagnóstico real (TESTAR_FONTES.bat)."""
import json
import unittest

import Caca_Arte_Scout as app
from scout_engine import adapters


def fake_fetch(pages):
    calls = []

    def fetch(url, timeout=12):
        calls.append(url)
        for key, value in pages.items():
            if key == url or (key.endswith("*") and url.startswith(key[:-1])):
                if isinstance(value, Exception):
                    raise value
                return value.encode("utf-8")
        raise RuntimeError("HTTP 404 em teste: " + url)
    fetch.calls = calls
    return fetch


SM_ARTIST = """<html><body><h2>Obras de arte</h2>
<div class="item"><a href="/listagem/obras-de-arte/aparecem-e-desaparecem"><img src="/storage/a.webp" alt="">Aparecem e desaparecem</a><span>2005 · 28 x 42 cm · Disponível</span></div>
<div class="item"><a href="/listagem/obras-de-arte/o-envelope">O Envelope</a><span>2001 · Vendido</span></div>
<div class="item"><a href="/listagem/obras-de-arte/elementos-a-partir-de">Elementos a partir de Serigrafia</a><span>2002 Disponível</span></div>
<a href="/listagem/artistas/outro">Outro</a></body></html>"""

SM_DETAIL = """<html><head><meta property="og:image" content="https://www.saomamede.com/storage/x.webp">
<meta property="og:description" content="Técnica mista sobre papel"></head><body>1 200,00 €</body></html>"""


class SaoMamedeTests(unittest.TestCase):
    def test_extracts_works_without_artist_name_in_link(self):
        fetch = fake_fetch({
            "https://www.saomamede.com/listagem/artistas/cruzeiro-seixas": SM_ARTIST,
            "https://www.saomamede.com/listagem/obras-de-arte/*": SM_DETAIL,
        })
        rows = adapters.search_sao_mamede("Cruzeiro Seixas", "Todas", 10, fetch, app.PATTERNS)
        urls = [r["url"] for r in rows]
        self.assertIn("https://www.saomamede.com/listagem/obras-de-arte/aparecem-e-desaparecem", urls)
        self.assertNotIn("https://www.saomamede.com/listagem/obras-de-arte/o-envelope", urls)  # vendido
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r["source"] == "Galeria São Mamede" for r in rows))
        first = rows[0]
        self.assertTrue(first["image"].startswith("https://www.saomamede.com/storage/"))

    def test_category_filter(self):
        fetch = fake_fetch({
            "https://www.saomamede.com/listagem/artistas/cruzeiro-seixas": SM_ARTIST,
            "https://www.saomamede.com/listagem/obras-de-arte/*": "<html></html>",
        })
        rows = adapters.search_sao_mamede("Cruzeiro Seixas", "Serigrafias", 10, fetch, app.PATTERNS)
        self.assertEqual([r["title"] for r in rows], ["Elementos a partir de Serigrafia"])

    def test_missing_artist_page_is_empty_not_failure(self):
        # 404 = artista não representado pela galeria (verificado no GitHub, 23-11-2026)
        self.assertEqual(adapters.search_sao_mamede("Artista Inexistente", "Todas", 10, fake_fetch({}), app.PATTERNS), [])

    def test_other_errors_are_failures(self):
        with self.assertRaises(Exception):
            adapters.search_sao_mamede("X", "Todas", 10, fake_fetch({"https://www.saomamede.com/*": RuntimeError("HTTP 500")}), app.PATTERNS)


def olx_page(ads):
    state = {"listing": {"listing": {"ads": ads}}}
    return "<html><script>window.__PRERENDERED_STATE__= %s;</script></html>" % json.dumps(json.dumps(state))


OLX_ADS = [
    {"id": 1, "title": "Litografia Cruzeiro Seixas autenticada (série 25/25)", "url": "https://www.olx.pt/d/anuncio/litografia-cruzeiro-seixas-IDabc1.html",
     "description": "Assinada", "price": {"regularPrice": {"value": 500, "currencyCode": "EUR"}, "displayValue": "500 €"},
     "photos": ["https://ireland.apollo.olxcdn.com/v1/files/x/image;s={width}x{height}"], "createdTime": "2026-11-10T10:00:00+00:00",
     "location": {"cityName": "Lisboa"}},
    {"id": 2, "title": "Compro obras de Cruzeiro Seixas", "url": "https://www.olx.pt/d/anuncio/compro-IDabc2.html", "description": "", "price": None},
    {"id": 3, "title": "Sofá antigo", "url": "https://www.olx.pt/d/anuncio/sofa-IDabc3.html", "description": "Cruzeiro Seixas", "price": None},
    {"id": 4, "title": "Mesa de jantar", "url": "https://www.olx.pt/d/anuncio/mesa-IDabc4.html", "description": "nada", "price": None},
    {"id": 5, "title": "Cruzeiro Seixas | Serigrafia sobre Tela | Assinada", "url": "https://www.olx.pt/d/anuncio/serigrafia-IDabc5.html",
     "description": "", "price": {"displayValue": "600 €"}, "photos": []},
]


class OlxTests(unittest.TestCase):
    def test_parses_state_and_filters(self):
        fetch = fake_fetch({"https://www.olx.pt/ads/q-cruzeiro-seixas/": olx_page(OLX_ADS),
                            "https://www.olx.pt/ads/q-cruzeiro-seixas/?page=2": olx_page(OLX_ADS)})
        rows = adapters.search_olx("Cruzeiro Seixas", "Todas", 50, fetch, app.PATTERNS)
        titles = [r["title"] for r in rows]
        self.assertEqual(len(rows), 2, titles)
        self.assertEqual(rows[0]["price"], 500.0)
        self.assertEqual(rows[0]["listing_id"], "1")
        self.assertIn("600x450", rows[0]["image"])
        self.assertEqual(rows[1]["price"], 600.0)
        # página 2 só repete anúncios -> paginação pára (sem ciclo infinito)
        self.assertLessEqual(len(fetch.calls), 2)

    def test_category(self):
        fetch = fake_fetch({"https://www.olx.pt/ads/q-cruzeiro-seixas/*": olx_page(OLX_ADS)})
        rows = adapters.search_olx("Cruzeiro Seixas", "Serigrafias", 50, fetch, app.PATTERNS)
        self.assertEqual(len(rows), 1)

    def test_html_fallback(self):
        raw = '<div data-cy="l-card"><a href="/d/anuncio/gravura-cruzeiro-seixas-IDzz9.html"><h4>Gravura Cruzeiro Seixas</h4></a><p data-testid="ad-price">150 €</p></div>'
        fetch = fake_fetch({"https://www.olx.pt/ads/q-cruzeiro-seixas/*": raw})
        rows = adapters.search_olx("Cruzeiro Seixas", "Todas", 50, fetch, app.PATTERNS)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["price"], 150.0)

    def test_unreachable_raises(self):
        with self.assertRaises(RuntimeError):
            adapters.search_olx("Cruzeiro Seixas", "Todas", 50, fake_fetch({}), app.PATTERNS)


CJ_PAGE = """<html>
<a href="https://www.custojusto.pt/lisboa/imobiliario/apartamentos/apartamento-t1-novo-na-ajuda--45515110">Apartamento T1 Novo, na Ajuda</a> 349 000 €
<a href="/lisboa/desporto-lazer/livros/cruzeiro-seixas-catalogo-43675992">Catálogo Cruzeiro Seixas 1ª edição</a> <span>50 €</span>
</html>"""


class CustoJustoTests(unittest.TestCase):
    def test_requires_artist_name(self):
        fetch = fake_fetch({"https://www.custojusto.pt/portugal/q/cruzeiro%20seixas*": CJ_PAGE})
        rows = adapters.search_custojusto("Cruzeiro Seixas", "Todas", 50, fetch, app.PATTERNS)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["price"], 50.0)
        self.assertTrue(rows[0]["url"].endswith("43675992"))


LQ_HOME = """<html><form action="/" method="get"><input type="hidden" name="tipo" value="pesq">
<input type="text" name="palavra" placeholder="Pesquisar"></form></html>"""
LQ_RESULTS = """<html><div class="produto"><a href="/?tipo=livro&id=123"><img src="/img/123.jpg"></a>
<h3>CRUZEIRO SEIXAS. Poesia e Pintura</h3><span class="preco">35,00 €</span></div></html>"""


class BookshopTests(unittest.TestCase):
    def test_form_discovery_finds_real_parameter(self):
        urls = adapters.discover_search_urls(LQ_HOME, "https://www.livrariaalfarrabista.com", "Cruzeiro Seixas")
        self.assertEqual(urls, ["https://www.livrariaalfarrabista.com/?tipo=pesq&palavra=Cruzeiro+Seixas"])

    def test_liliana_queiroz_flow(self):
        fetch = fake_fetch({
            "https://www.livrariaalfarrabista.com": LQ_HOME,
            "https://www.livrariaalfarrabista.com/?tipo=pesq&palavra=Cruzeiro+Seixas": LQ_RESULTS,
            "https://www.livrariaalfarrabista.com/?tipo=livro&id=123": "<html></html>",
        })
        rows = adapters.search_bookshop_auto("Cruzeiro Seixas", "Livros", "Livraria Alfarrabista Liliana Queiroz",
                                             "https://www.livrariaalfarrabista.com", fetch, app._CardParser.cards,
                                             app.PATTERNS)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["price"], 35.0)
        self.assertTrue(rows[0]["image"].endswith("/img/123.jpg"))

    def test_missing_query_page_is_not_silent_success(self):
        fetch = fake_fetch({
            "https://www.livrariaalfarrabista.com": "<html>sem formulário</html>",
            "https://www.livrariaalfarrabista.com/?tipo=pesq&pesq=x": "<html>Falta a pesquisa</html>",
        })
        with self.assertRaises(RuntimeError):
            adapters.search_bookshop_auto("x", "Todas", "L", "https://www.livrariaalfarrabista.com", fetch,
                                          app._CardParser.cards, app.PATTERNS,
                                          fallback_urls=["https://www.livrariaalfarrabista.com/?tipo=pesq&pesq=x"])

    def test_author_confirmed_on_detail_page(self):
        results = """<div class="produto"><a href="/livro/1/aguarelas"><h3>AGUARELAS.</h3></a><span class="price">50,00 €</span></div>"""
        detail = """<html><head><meta property="og:image" content="/img/1.jpg"></head><body>Autor: Cruzeiro Seixas</body></html>"""
        fetch = fake_fetch({
            "https://www.sadacosta.com": "<html></html>",
            "https://www.sadacosta.com/livros?pesquisa=Cruzeiro%20Seixas": results,
            "https://www.sadacosta.com/livro/1/aguarelas": detail,
        })
        rows = adapters.search_bookshop_auto("Cruzeiro Seixas", "Todas", "Livraria Sá da Costa", "https://www.sadacosta.com",
                                             fetch, app._CardParser.cards, app.PATTERNS,
                                             fallback_urls=["https://www.sadacosta.com/livros?pesquisa=Cruzeiro%20Seixas"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["image"], "https://www.sadacosta.com/img/1.jpg")


class PriceTests(unittest.TestCase):
    def test_formats(self):
        P = adapters.parse_price
        self.assertEqual(P("1 800,00 €"), 1800.0)
        self.assertEqual(P("€1.250,50"), 1250.5)
        self.assertEqual(P("349 000 €"), 349000.0)
        self.assertEqual(P("35,00 €"), 35.0)
        self.assertEqual(P("600 €"), 600.0)
        self.assertEqual(P("€ 1,200.00"), 1200.0)
        self.assertIsNone(P("sem preço"))


class AppIntegrationTests(unittest.TestCase):
    def test_no_all_areas_search(self):
        with self.assertRaises(ValueError):
            app.resolve_sources("Todas as fontes")
        self.assertIn("OLX", app.resolve_sources("Usados, arte e livros"))
        self.assertNotIn("OLX", app.resolve_sources("Fontes de arte"))
        self.assertNotIn("P55.art", app.resolve_sources("Fontes de livros"))

    def test_failure_isolation_and_metadata(self):
        original = app.search_one
        try:
            def fake(source, name, category, limit, warnings=None):
                if source == "OLX":
                    raise RuntimeError("simulado")
                return [{"artist": name, "title": "x", "price": 10.0, "price_text": "€10,00",
                         "url": "https://example.org/%s?utm_source=a" % source.replace(" ", ""), "source": source}]
            app.search_one = fake
            app.time.sleep = lambda s: None
            rows, errors = app.do_search("Cruzeiro Seixas", "Todas", 5, None, "Usados, arte e livros")
        finally:
            app.search_one = original
        self.assertEqual(len(errors), 1)
        self.assertTrue(errors[0].startswith("OLX"))
        self.assertGreater(len(rows), 5)
        for r in rows:
            self.assertEqual(r["area"], "Usados")
            self.assertTrue(r["collected_at"])
            self.assertEqual(len(r["dedup_key"]), 16)

    def test_dedup_merges_missing_fields(self):
        original = app.search_one
        try:
            def fake(source, name, category, limit, warnings=None):
                img = "https://img/x.jpg" if source == "ZVAB" else ""
                return [{"artist": name, "title": "x", "price": None, "price_text": "Preço não indicado",
                         "url": "https://www.example.org/livro/1/", "source": source, "image": img}]
            app.search_one = fake
            app.time.sleep = lambda s: None
            rows, _ = app.do_search("A", "Todas", 5, None, "Fontes de livros")
        finally:
            app.search_one = original
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["image"], "https://img/x.jpg")

    def test_direct_fallback_to_search_engine(self):
        orig_olx, orig_ext = app.DIRECT_USED["OLX"], app.search_external
        try:
            app.DIRECT_USED["OLX"] = lambda a, c, l: (_ for _ in ()).throw(RuntimeError("bloqueado"))
            app.search_external = lambda a, c, s, l: [{"url": "https://www.olx.pt/d/anuncio/x.html", "title": "x", "price": None}]
            warnings = []
            rows = app.search_one("OLX", "Cruzeiro Seixas", "Todas", 5, warnings)
        finally:
            app.DIRECT_USED["OLX"], app.search_external = orig_olx, orig_ext
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(warnings), 1)


if __name__ == "__main__":
    unittest.main()
