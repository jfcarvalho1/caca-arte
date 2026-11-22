def extract_page_metadata(html_text, url=None):
    """Extrai texto e metadados de uma página; nunca inventa preço ou disponibilidade."""
    try:
        import trafilatura
        from trafilatura.metadata import extract_metadata
        text=trafilatura.extract(html_text, url=url, include_comments=False, include_tables=True) or ""
        meta=extract_metadata(html_text, default_url=url)
        return {"text":text, "title":getattr(meta,"title",None), "description":getattr(meta,"description",None),
                "image":getattr(meta,"image",None), "url":getattr(meta,"url",None)}
    except ImportError as exc:
        raise RuntimeError("Trafilatura não está instalada neste ambiente") from exc
