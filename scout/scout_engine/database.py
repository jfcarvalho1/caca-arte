import json, sqlite3, threading
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timezone

class ResultStore:
    def __init__(self, path=None):
        import sys as _sys
        # No .exe (PyInstaller) os dados ficam ao lado do programa, não na pasta temporária.
        _base = Path(_sys.executable).resolve().parent if getattr(_sys, "frozen", False) else Path(__file__).resolve().parent.parent
        self.path = Path(path) if path else _base / "data" / "scout_results.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        with self._connect() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY, canonical_url TEXT NOT NULL UNIQUE,
                artist TEXT, title TEXT NOT NULL, source TEXT, price REAL,
                price_text TEXT, image TEXT, description TEXT, availability TEXT,
                shipping TEXT, area TEXT, query_artist TEXT, first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL, raw_json TEXT NOT NULL)""")
            c.execute("CREATE INDEX IF NOT EXISTS idx_results_artist ON results(artist)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_results_source ON results(source)")
            try:
                c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS results_fts USING fts5(title, artist, description, content='results', content_rowid='id')")
            except sqlite3.OperationalError:
                pass
    @contextmanager
    def _connect(self):
        """Abre uma ligação SQLite e garante transacção e fecho da ligação."""
        c=sqlite3.connect(str(self.path), timeout=20)
        c.row_factory=sqlite3.Row
        try:
            with c:
                yield c
        finally:
            c.close()
    def save_results(self, rows, query_artist="", area=""):
        now=datetime.now(timezone.utc).isoformat()
        saved=0
        with self.lock, self._connect() as c:
            for row in rows:
                url=(row.get("url") or "").split("#",1)[0].rstrip("/")
                if not url.startswith(("http://","https://")): continue
                payload=dict(row)
                c.execute("""INSERT INTO results(canonical_url,artist,title,source,price,price_text,image,description,availability,shipping,area,query_artist,first_seen,last_seen,raw_json)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(canonical_url) DO UPDATE SET
                artist=excluded.artist,title=excluded.title,source=excluded.source,
                price=excluded.price,price_text=excluded.price_text,image=excluded.image,
                description=excluded.description,availability=excluded.availability,
                shipping=excluded.shipping,area=excluded.area,query_artist=excluded.query_artist,
                last_seen=excluded.last_seen,raw_json=excluded.raw_json""",
                (url,row.get("artist"),row.get("title") or url,row.get("source"),row.get("price"),
                 row.get("price_text"),row.get("image"),row.get("description"),row.get("availability"),
                 row.get("shipping"),area,query_artist,now,now,json.dumps(payload,ensure_ascii=False)))
                saved+=1
            # Rebuild FTS index safely; availability of FTS5 is checked at initialisation.
            try: c.execute("INSERT INTO results_fts(results_fts) VALUES('rebuild')")
            except sqlite3.OperationalError: pass
        return saved
    @staticmethod
    def _rows(rows):
        out = []
        for r in rows:
            item = json.loads(r["raw_json"])
            item["first_seen"] = r["first_seen"]
            item["last_seen"] = r["last_seen"]
            out.append(item)
        return out

    def search(self, term, limit=100):
        """Pesquisa no histórico local (título, artista, descrição, fonte)."""
        like = f"%{term}%"
        with self._connect() as c:
            rows = c.execute("SELECT raw_json, first_seen, last_seen FROM results WHERE title LIKE ? OR artist LIKE ? "
                             "OR description LIKE ? OR source LIKE ? ORDER BY last_seen DESC LIMIT ?",
                             (like, like, like, like, limit)).fetchall()
        return self._rows(rows)

    def recent(self, limit=200):
        with self._connect() as c:
            rows = c.execute("SELECT raw_json, first_seen, last_seen FROM results ORDER BY last_seen DESC, id DESC LIMIT ?",
                             (limit,)).fetchall()
        return self._rows(rows)

    def first_seen_map(self, urls):
        """URL canónico -> data em que o anúncio foi visto pela primeira vez."""
        keys = [(u or "").split("#", 1)[0].rstrip("/") for u in urls]
        out = {}
        with self._connect() as c:
            for i in range(0, len(keys), 500):
                chunk = keys[i:i + 500]
                q = "SELECT canonical_url, first_seen FROM results WHERE canonical_url IN (%s)" % ",".join("?" * len(chunk))
                for r in c.execute(q, chunk).fetchall():
                    out[r["canonical_url"]] = r["first_seen"]
        return out

    def count(self):
        with self._connect() as c: return c.execute("SELECT COUNT(*) FROM results").fetchone()[0]
