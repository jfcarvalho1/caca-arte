# -*- coding: utf-8 -*-
"""Testes dos motores de galerias (0.4.4), com HTML/JSON copiados da estrutura real."""
import json, unittest
import Caca_Arte_Scout as app
from scout_engine import adapters
from test_adapters_040 import fake_fetch

CPS = '''<a href="/pt/loja/ex0074"> <div class="ws-works-offer text-center"> <div class="ws-journal-image"> <figure> <img src="/media/x/ex0074.jpg" alt="Paquete III"> </figure> </div> <div class="product ws-works-caption text-cente"> <div class="ws-item-category">Paquete III</div> <h3 class="ws-item-title">Júlio Pomar</h3> <div class="ws-item-separator"></div> <div class="price"> <span class="price-customer">1100€</span><br> <span class="regular">Sócios:</span> 850€ </div> </div> </div> </a>
<a href="/pt/loja/nl023"> <div><img src="/media/x/nl023.jpg"><div class="ws-item-category">Pessoa</div> <h3 class="ws-item-title">Júlio Pomar</h3> Esgotado</div></a>'''

ART4ALL = '''<div class="product-block-inner"> <div class="image"> <a href="https://www.art4all.pt/index.php?route=product/product&amp;product_id=1155&amp;search=pomar"> <img src="https://www.art4all.pt/image/03JP008.jpg" title="Júlio Pomar - Camões" alt="Júlio Pomar - Camões"></a></div> <p class="price"> 720,00€ </p></div>'''

CULT_LIST = "<a href='artistas-75-Alfredo Luz'>Alfredo Luz</a><a href='artistas-8-António Neves'>x</a>"
CULT_PAGE = ("<div class='grelha-items'><a href='detalhes-1569-Sem T&#237;tulo' title='Sem Título'><img src='obras/AL_1793w1.jpg'/></a><h3 class='sub1'>Sem Título</h3>"
             "<h3 class='sub'><a href='artistas-75-Alfredo Luz'>Alfredo Luz</a></h3><div><span class='texto'>Acr&#237;lico sobre cart&#227;o&nbsp;&Iota;&nbsp;20x20 cm</span><br/></div>"
             "<div id='parte2_1'><div id='parte2_1_1'><span class='texto'>1.300&nbsp;€</span></div></div></div>")

class GalleryTests(unittest.TestCase):
    def test_cps(self):
        rows = adapters.search_cps("Júlio Pomar", "Todas", 50, fake_fetch({"https://www.cps.pt/pt/search/*": CPS}), app.PATTERNS)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["price"], 1100.0)
        self.assertEqual(rows[0]["url"], "https://www.cps.pt/pt/loja/ex0074")

    def test_art4all(self):
        rows = adapters.search_art4all("Júlio Pomar", "Todas", 50, fake_fetch({"https://www.art4all.pt/*": ART4ALL}), app.PATTERNS)
        self.assertEqual(rows[0]["price"], 720.0)
        self.assertIn("product_id=1155", rows[0]["url"])

    def test_culturas(self):
        f = fake_fetch({"https://www.culturas.pt/artistas": CULT_LIST, "https://www.culturas.pt/artistas-75*": CULT_PAGE})
        rows = adapters.search_culturas("Alfredo Luz", "Todas", 50, f, app.PATTERNS)
        self.assertEqual(rows[0]["price"], 1300.0)
        self.assertTrue(rows[0]["image"].endswith("obras/AL_1793w1.jpg"))
        self.assertEqual(adapters.search_culturas("Paula Rego", "Todas", 50, f, app.PATTERNS), [])

    def test_shopify_suggest(self):
        sug = {"resources": {"results": {"products": [
            {"title": "Prisma – Vhils Special Edition", "url": "/products/prisma?_pos=3", "price": "450.00", "available": True, "featured_image": {"url": "https://cdn/x.jpg"}},
            {"title": "VHILS collection", "url": "/products/v2", "price": "30.00", "available": False}]}}}
        f = fake_fetch({"https://www.under-dogs.net/search/suggest.json*": json.dumps(sug)})
        rows = adapters.search_shopify_store("Vhils", "Todas", 50, f, app.PATTERNS, "https://www.under-dogs.net", "Underdogs Gallery")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["url"], "https://www.under-dogs.net/products/prisma")
        self.assertEqual(rows[0]["price"], 450.0)

    def test_woocommerce(self):
        data = [{"name": "Júlio Pomar - Serigrafia", "permalink": "https://twoart.net/p/1", "description": "", "is_in_stock": True,
                 "prices": {"price": "45000", "currency_minor_unit": 2}, "images": [{"src": "https://twoart.net/i.jpg"}]},
                {"name": "Júlio Pomar - Vendida", "permalink": "https://twoart.net/p/2", "is_in_stock": False, "prices": {}}]
        f = fake_fetch({"https://twoart.net/wp-json/*": json.dumps(data)})
        rows = adapters.search_woocommerce_store("Júlio Pomar", "Todas", 50, f, app.PATTERNS, "https://twoart.net", "TWOART Gallery")
        self.assertEqual([r["price"] for r in rows], [450.0])

    def test_art_area_has_no_dead_sources(self):
        arts = app.resolve_sources("Fontes de arte")
        for dead in app.DISABLED_SOURCES:
            self.assertNotIn(dead, arts)

if __name__ == "__main__":
    unittest.main()
