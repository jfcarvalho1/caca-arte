# -*- coding: utf-8 -*-
"""Testes da correcção 0.4.1 (P55: certificado e erros silenciosos)."""
import ssl, unittest
from urllib.error import URLError
import Caca_Arte_Scout as app


class FakeResp:
    status = 200
    def __init__(self, data): self.data = data
    def read(self): return self.data
    def __enter__(self): return self
    def __exit__(self, *a): return False


class SslFallbackTests(unittest.TestCase):
    def setUp(self):
        self.orig = (app.urlopen, app._SSL_CONTEXTS)
        app._HTTP_CACHE.clear()

    def tearDown(self):
        app.urlopen, app._SSL_CONTEXTS = self.orig

    def test_second_context_used_when_first_rejects_certificate(self):
        used = []
        def fake(req, timeout=12, context=None):
            used.append(context)
            if context == "A":
                raise URLError(ssl.SSLCertVerificationError(1, "certificate has expired"))
            return FakeResp(b"ok")
        app.urlopen = fake
        app._SSL_CONTEXTS = [("certifi", "A"), ("sistema", "B")]
        self.assertEqual(app.get("https://www.p55.art/x"), b"ok")
        self.assertEqual(used, ["A", "B"])

    def test_all_contexts_rejected_gives_clear_error(self):
        def fake(req, timeout=12, context=None):
            raise URLError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: certificate has expired")
        app.urlopen = fake
        app._SSL_CONTEXTS = [("certifi", "A"), ("sistema", "B")]
        with self.assertRaises(RuntimeError) as cm:
            app.get("https://www.p55.art/y")
        self.assertIn("Certificado", str(cm.exception))

    def test_verification_never_disabled(self):
        for name, ctx in app._build_ssl_contexts():
            self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED, name)
            self.assertTrue(ctx.check_hostname, name)


class P55ErrorSurfacingTests(unittest.TestCase):
    def test_unreachable_p55_is_failure_not_empty(self):
        orig = app.get
        try:
            def boom(url, timeout=12):
                raise RuntimeError("Certificado de segurança recusado por www.p55.art")
            app.get = boom
            with self.assertRaises(RuntimeError) as cm:
                app.search_artist("Cruzeiro Seixas", "Todas", 50)
            self.assertIn("P55.art inacessível", str(cm.exception))
        finally:
            app.get = orig

    def test_non_ascii_handle_in_html(self):
        p = app._P55ProductLinkParser()
        p.feed('<a href="/products/cruzeiro-seixas-serigrafia-nº123-150">x</a>')
        self.assertIn("cruzeiro-seixas-serigrafia-nº123-150", p.links)


if __name__ == "__main__":
    unittest.main()
