"""
Keyword extraction with YAKE — unsupervised, statistical, no model
download or GPU needed, and fast enough to run on the full transcript
rather than per-chunk.
"""


def extract_keywords(text: str, top_n: int = 12) -> list[dict]:
    if not text.strip():
        return []
    try:
        import yake
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "The keyword extractor requires 'yake'. Install it with: "
            "pip install yake"
        ) from exc

    extractor = yake.KeywordExtractor(
        lan="en",
        n=2,  # up to 2-word phrases
        dedupLim=0.7,
        top=top_n,
    )
    # YAKE scores are "lower is better" (distance-like); invert to a
    # 0-100 relevance score that's friendlier to show in a UI.
    raw = extractor.extract_keywords(text)
    if not raw:
        return []
    max_score = max(score for _, score in raw) or 1
    return [
        {
            "keyword": kw,
            "relevance": round(100 * (1 - score / max_score), 1),
        }
        for kw, score in raw
    ]