import importlib.util
import json
import pathlib
import sys
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("scout_main", ROOT / "Caca_Arte_Scout.py")
scout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scout)


class P55ConnectorTests(unittest.TestCase):
    def product(self, ident, title, available=True, price="100.00"):
        return {
            "id": ident, "handle": f"obra-{ident}", "title": title,
            "body_html": "Obra de arte sobre papel",
            "tags": ["José de Guimarães"],
            "variants": [{"available": available, "price": price}],
            "images": [{"src": f"https://cdn.example/{ident}.jpg"}],
        }

    def test_collection_products_paginates_and_deduplicates(self):
        page1 = [self.product(i, f"Obra {i}") for i in range(1, 251)]
        page2 = [self.product(251, "Obra 251")]
        calls = []

        def fake_get(url, timeout=12):
            calls.append(url)
            page = page1 if "page=1" in url else page2 if "page=2" in url else []
            return json.dumps({"products": page}).encode()

        with patch.object(scout, "get", side_effect=fake_get):
            products = scout._p55_collection_products("jose-de-guimaraes")

        self.assertEqual(len(products), 251)
        self.assertEqual(len(calls), 2)

    def test_search_artist_keeps_available_and_excludes_unavailable(self):
        products = [
            self.product(1, "Serigrafia disponível", True, "125.00"),
            self.product(2, "Guache disponível", True, "250.00"),
            self.product(3, "Obra indisponível", False, "300.00"),
        ]

        def fake_get(url, timeout=12):
            return json.dumps({"products": products if "page=1" in url else []}).encode()

        with patch.object(scout, "get", side_effect=fake_get):
            results = scout.search_artist("José de Guimarães", "Todas", 100)

        self.assertEqual(len(results), 2)
        self.assertEqual([r["price"] for r in results], [125.0, 250.0])
        self.assertTrue(all(r["source"] == "P55.art" for r in results))

    def test_search_artist_returns_more_than_50_results_for_catalogue_pagination(self):
        products = [self.product(i, f"Obra {i}", True, str(100 + i)) for i in range(1, 108)]

        def fake_get(url, timeout=12):
            return json.dumps({"products": products if "page=1" in url else []}).encode()

        with patch.object(scout, "get", side_effect=fake_get):
            results = scout.search_artist("José de Guimarães", "Todas", 250)

        self.assertEqual(len(results), 107)

    def test_available_listing_not_discarded_because_description_mentions_sold_out_edition(self):
        product = self.product(900, "Serigrafia sobre papel artesanal", True, "2025.00")
        product["body_html"] = "Edição já esgotada junto do editor, exemplar disponível na galeria."

        def fake_get(url, timeout=12):
            return json.dumps({"products": [product] if "page=1" in url else []}).encode()

        with patch.object(scout, "get", side_effect=fake_get):
            results = scout.search_artist("José de Guimarães", "Todas", 250)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["price"], 2025.0)


    def test_html_collection_fallback_extracts_product_handles_and_product_js(self):
        class FakeResponse:
            pass
        html_page = b'<a href="/products/obra-a">A</a><a href="/products/obra-b">B</a>'
        product_a = self.product(501, "Obra A") | {"handle": "obra-a"}
        product_b = self.product(502, "Obra B") | {"handle": "obra-b"}
        def fake_get(url, timeout=12):
            if "/collections/" in url:
                return html_page
            if "/products/obra-a.js" in url:
                return json.dumps(product_a).encode()
            if "/products/obra-b.js" in url:
                return json.dumps(product_b).encode()
            return b''
        with patch.object(scout, "get", side_effect=fake_get):
            products = scout._p55_collection_html_products("jose-de-guimaraes")
        self.assertEqual({p["handle"] for p in products}, {"obra-a", "obra-b"})

    def test_html_fallback_keeps_paging_when_page_has_fewer_than_12_products(self):
        page1 = ''.join(f'<a href="/products/obra-{i}">Obra {i}</a>' for i in range(1, 12)).encode()
        page2 = b'<a href="/products/obra-12">Obra 12</a><a href="/products/obra-13">Obra 13</a>'
        products = []
        calls = []
        def fake_get(url, timeout=12):
            calls.append(url)
            if '/collections/' in url:
                return page1 if 'page=1' in url else page2 if 'page=2' in url else b''
            handle = url.rsplit('/products/', 1)[-1].replace('.js', '')
            ident = int(handle.split('-')[-1])
            return json.dumps(self.product(ident, f'Obra {ident}') | {'handle': handle}).encode()
        with patch.object(scout, 'get', side_effect=fake_get):
            products = scout._p55_collection_html_products('artista')
        self.assertEqual(len(products), 13)
        self.assertTrue(any('page=2' in url for url in calls))

    def test_search_artist_uses_html_fallback_when_collection_json_fails(self):
        product = self.product(701, "Serigrafia José de Guimarães") | {"handle": "obra-jg"}
        def fake_get(url, timeout=12):
            if "/products.json" in url:
                raise RuntimeError("endpoint indisponível")
            if "/collections/" in url:
                return b'<a href="/products/obra-jg">Obra</a>'
            if "/products/obra-jg.js" in url:
                return json.dumps(product).encode()
            return b''
        with patch.object(scout, "get", side_effect=fake_get):
            results = scout.search_artist("José de Guimarães", "Todas", 250)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["url"], "https://www.p55.art/products/obra-jg")


if __name__ == "__main__":
    unittest.main()
