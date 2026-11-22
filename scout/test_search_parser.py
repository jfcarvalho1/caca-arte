import unittest
import unittest.mock
from unittest.mock import patch
import Caca_Arte_Scout as scout

class SearchParserTests(unittest.TestCase):
    def test_bing_fallback_extracts_domain_anchor(self):
        html = '<html><a href="https://www.111.pt/obra/123"><h2>José de Guimarães, obra</h2></a></html>'
        with patch.object(scout, "get", return_value=html.encode()):
            rows = scout._engine_results("Bing", "artist", "111.pt")
        self.assertEqual(len(rows), 1)
        self.assertIn("111.pt/obra/123", rows[0][1])

    def test_duckduckgo_unwraps_redirect(self):
        from urllib.parse import quote
        target = "https://www.under-dogs.net/artwork/abc"
        redirect = "https://duckduckgo.com/l/?uddg=" + quote(target, safe="")
        html = f'<a class="result__a" href="{redirect}">Artwork José de Guimarães</a>'
        with patch.object(scout, "get", return_value=html.encode()):
            rows = scout._engine_results("DuckDuckGo", "artist", "under-dogs.net")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], target)

    def test_rejects_other_domains(self):
        html = '<a href="https://example.com/item"><h2>José de Guimarães</h2></a>'
        with patch.object(scout, "get", return_value=html.encode()):
            rows = scout._engine_results("Bing", "artist", "111.pt")
        self.assertEqual(rows, [])

if __name__ == "__main__":
    unittest.main()


class LegacyFirstRegressionTests(unittest.TestCase):
    def test_original_extractor_is_preferred_when_it_returns_results(self):
        import Caca_Arte_Scout as scout
        legacy = [("Obra original", "https://exemplo.pt/obra", "resultado")]
        with unittest.mock.patch.object(scout, "_engine_results_legacy", return_value=legacy), \
             unittest.mock.patch.object(scout, "_engine_results_enhanced", side_effect=AssertionError("não devia ser chamado")):
            self.assertEqual(scout._engine_results("Bing", "teste", "exemplo.pt"), legacy)

    def test_enhanced_extractor_remains_as_fallback(self):
        import Caca_Arte_Scout as scout
        enhanced = [("Obra alternativa", "https://exemplo.pt/obra2", "resultado")]
        with unittest.mock.patch.object(scout, "_engine_results_legacy", return_value=[]), \
             unittest.mock.patch.object(scout, "_engine_results_enhanced", return_value=enhanced):
            self.assertEqual(scout._engine_results("Bing", "teste", "exemplo.pt"), enhanced)
