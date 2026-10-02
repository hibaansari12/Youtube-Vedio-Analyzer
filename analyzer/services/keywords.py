"""Extract transcript keywords with semantic embeddings and diversity ranking."""

import re

_GENERIC_TERMS = {
    "back",
    "challenge",
    "challenged",
    "challenging",
    "inside",
    "turn",
    "turned",
    "turns",
    "work",
    "working",
    "works",
}
_keyword_model = None


def _get_keyword_model():
    global _keyword_model
    if _keyword_model is None:
        try:
            from keybert import KeyBERT
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "The keyword extractor requires 'keybert'. Install it with: "
                "pip install keybert"
            ) from exc
        _keyword_model = KeyBERT(model="all-MiniLM-L6-v2")
    return _keyword_model


def extract_keywords(text: str, top_n: int = 12) -> list[dict]:
    if not text.strip() or top_n <= 0:
        return []

    raw = _get_keyword_model().extract_keywords(
        text,
        keyphrase_ngram_range=(1, 2),
        stop_words="english",
        use_mmr=True,
        diversity=0.7,
        top_n=top_n * 3,
    )
    if not raw:
        return []

    transcript_tokens = re.findall(r"[a-z0-9]+", text.lower())
    candidates = []
    for keyword, score in raw:
        tokens = re.findall(r"[a-z0-9]+", keyword.lower())
        if not tokens or any(token in _GENERIC_TERMS for token in tokens):
            continue
        if len(tokens) > 1 and not any(
            transcript_tokens[index : index + len(tokens)] == tokens
            for index in range(len(transcript_tokens) - len(tokens) + 1)
        ):
            continue
        candidates.append((keyword, score, tokens))

    phrase_tokens = [set(tokens) for _, _, tokens in candidates if len(tokens) > 1]
    selected = []
    for keyword, score, tokens in candidates:
        token_set = set(tokens)
        if len(tokens) == 1 and any(tokens[0] in phrase for phrase in phrase_tokens):
            continue
        if any(
            len(token_set & prior_tokens) / min(len(token_set), len(prior_tokens)) >= 0.6
            for _, _, prior_tokens in selected
        ):
            continue
        selected.append((keyword, score, token_set))
        if len(selected) == top_n:
            break

    if not selected:
        return []

    return [
        {
            "keyword": keyword,
            "relevance": round(max(0.0, min(100.0, score * 100)), 1),
        }
        for keyword, score, _ in selected
    ]