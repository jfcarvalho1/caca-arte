from playwright.sync_api import sync_playwright
def fetch_rendered(url, timeout_ms=30000):
    """Obter HTML renderizado em Chromium. Não contorna login, CAPTCHA ou bloqueios."""
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        try:
            page=browser.new_page()
            response=page.goto(url,wait_until="domcontentloaded",timeout=timeout_ms)
            page.wait_for_timeout(1200)
            return {"status": response.status if response else None, "url":page.url, "html":page.content()}
        finally:
            browser.close()
