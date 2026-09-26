"""
Chunk + summarize. Long transcripts (1hr+ videos) get split into
model-sized pieces, each summarized independently, then the partial
summaries are combined and summarized once more into a final summary.
This "map-reduce" approach keeps quality up without truncating content.
"""

_summarizer = None
MODEL_NAME = "facebook/bart-large-cnn"

# BART's practical input limit is ~1024 tokens; we chunk on words as a
# cheap proxy (~1 token ≈ 0.75 words for English) and stay well under it.
WORDS_PER_CHUNK = 650


def _get_summarizer():
    global _summarizer
    if _summarizer is None:
        try:
            from transformers import pipeline
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "The summarizer requires 'transformers' and 'torch'. "
                "Install them with: pip install transformers torch"
            ) from exc

        _summarizer = pipeline("summarization", model=MODEL_NAME, device=0)
    return _summarizer


def chunk_text(text: str, words_per_chunk: int = WORDS_PER_CHUNK) -> list[str]:
    words = text.split()
    if not words:
        return []
    return [
        " ".join(words[i : i + words_per_chunk])
        for i in range(0, len(words), words_per_chunk)
    ]


def _summarize_one(text: str, max_len: int = 180, min_len: int = 40) -> str:
    word_count = len(text.split())
    if word_count < 20:
        return text  # too short to meaningfully summarize
    # Keep the model's max/min sane relative to input length.
    max_len = min(max_len, max(min_len + 10, word_count // 2))
    summarizer = _get_summarizer()
    result = summarizer(
        text, max_length=max_len, min_length=min(min_len, max_len - 5), do_sample=False
    )
    return result[0]["summary_text"].strip()


def summarize_long_text(text: str) -> dict:
    chunks = chunk_text(text)
    if not chunks:
        return {"summary": "", "chunk_count": 0, "chunk_summaries": []}

    chunk_summaries = [_summarize_one(c) for c in chunks]

    if len(chunk_summaries) == 1:
        final_summary = chunk_summaries[0]
    else:
        combined = " ".join(chunk_summaries)
        # Reduce step: summarize the combined partial summaries once more.
        final_summary = _summarize_one(combined, max_len=220, min_len=60)

    return {
        "summary": final_summary,
        "chunk_count": len(chunks),
        "chunk_summaries": chunk_summaries,
    }