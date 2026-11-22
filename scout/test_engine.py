import tempfile, unittest
from pathlib import Path
from scout_engine.database import ResultStore
from scout_engine.normalization import artist_match_score, fold
from scout_engine.connectors import list_sources

class ScoutEngineTests(unittest.TestCase):
    def test_normalization_accent_and_case(self):
        self.assertEqual(fold("JOSÉ de Guimarães"),"jose de guimaraes")
        self.assertEqual(artist_match_score("José de Guimarães","Jose De Guimaraes, serigrafia"),100)
    def test_all_artist_names_have_accent_insensitive_variants(self):
        from scout_engine.normalization import ALIASES, ARTISTS
        self.assertEqual(len(ARTISTS), 13)
        for artist in ARTISTS:
            self.assertIn(artist, ALIASES)
            folded = fold(artist)
            self.assertTrue(any(fold(v) == folded for v in ALIASES[artist]))

    def test_persistent_store_and_upsert(self):
        with tempfile.TemporaryDirectory() as d:
            db=ResultStore(Path(d)/"test.sqlite3")
            row={"artist":"José de Guimarães","title":"Serigrafia teste","url":"https://example.org/item/1","source":"Teste","price":50.0,"description":"Obra gráfica"}
            self.assertEqual(db.save_results([row],"José de Guimarães","Arte"),1)
            self.assertEqual(db.save_results([row],"José de Guimarães","Arte"),1)
            self.assertEqual(db.count(),1)
    def test_invalid_url_not_saved(self):
        with tempfile.TemporaryDirectory() as d:
            db=ResultStore(Path(d)/"test.sqlite3")
            self.assertEqual(db.save_results([{"title":"x","url":"javascript:alert(1)"}]),0)
            self.assertEqual(db.count(),0)
    def test_source_registry_is_explicit(self):
        all_sources=list_sources()
        self.assertGreaterEqual(len(all_sources),40)
        self.assertIn("P55.art",all_sources)
        self.assertIn("AbeBooks",all_sources)

if __name__=="__main__": unittest.main()
