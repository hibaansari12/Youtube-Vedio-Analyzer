"""Generate a transcript summary with the local BART summarization model."""

import re
from collections import Counter
from collections.abc import Callable

MODEL_NAME = "facebook/bart-large-cnn"
WORDS_PER_CHUNK = 350
SUMMARIZATION_BATCH_SIZE = 4
_summarizer = None


def _get_summarizer():
    global _summarizer
    if _summarizer is None:
        try:
            import torch
            from transformers import AutoTokenizer, pipeline
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "BART summarization requires 'transformers' and 'torch'. "
                "Install project dependencies with: pip install -r requirements.txt"
            ) from exc

        device = 0 if torch.cuda.is_available() else -1
        tokenizer = AutoTokenizer.from_pretrained(
            MODEL_NAME, clean_up_tokenization_spaces=True
        )
        _summarizer = pipeline(
            "summarization",
            model=MODEL_NAME,
            tokenizer=tokenizer,
            device=device,
        )
    return _summarizer


def split_words(text: str, words_per_chunk: int = WORDS_PER_CHUNK) -> list[str]:
    words = text.split()
    if words_per_chunk < 1:
        raise ValueError("words_per_chunk must be greater than zero.")
    return [
        " ".join(words[index : index + words_per_chunk])
        for index in range(0, len(words), words_per_chunk)
    ]


def _summarize_many(
    texts: list[str],
    summarizer,
    max_length: int = 120,
    min_length: int = 20,
) -> list[str]:
    summaries = [""] * len(texts)
    pending = [
        (index, text)
        for index, text in enumerate(texts)
        if len(text.split()) >= 20
    ]
    for index, text in enumerate(texts):
        if len(text.split()) < 20:
            summaries[index] = text.strip()

    if not pending:
        return summaries

    results = summarizer(
        [text for _, text in pending],
        batch_size=SUMMARIZATION_BATCH_SIZE,
        max_length=max_length,
        min_length=min(min_length, max_length - 5),
        do_sample=False,
    )
    if not isinstance(results, list) or len(results) != len(pending):
        raise RuntimeError("BART returned an incomplete transcript summary batch.")

    for (index, _), result in zip(pending, results):
        summary = result.get("summary_text") if isinstance(result, dict) else None
        if not isinstance(summary, str) or not summary.strip():
            raise RuntimeError("BART returned an empty summary for a transcript section.")
        summaries[index] = summary.strip()
    return summaries


def _split_sentences(text: str) -> list[str]:
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?।])\s+", text.strip())
        if sentence.strip()
    ]


def _deduplicate_sentences(sentences: list[str]) -> list[str]:
    unique = []
    seen = set()
    for sentence in sentences:
        normalized = re.sub(r"[^\w]+", " ", sentence.casefold()).strip()
        if normalized and normalized not in seen:
            unique.append(sentence)
            seen.add(normalized)
    return unique


def _limit_words(text: str, word_limit: int) -> str:
    words = text.split()
    if len(words) <= word_limit:
        return text
    return " ".join(words[:word_limit]).rstrip(" ,;:") + "."


def _is_degenerate(text: str) -> bool:
    words = re.findall(r"\b[\w']+\b", text.casefold())
    if not words:
        return True
    if len(words) < 12:
        return False
    if len(set(words)) / len(words) < 0.35:
        return True
    repeated_phrases = Counter(
        tuple(words[index : index + 4]) for index in range(len(words) - 3)
    )
    return any(
        count >= 3 and count * 4 >= len(words) * 0.5
        for count in repeated_phrases.values()
    )


def summarize_long_text(
    text: str, progress_callback: Callable[[str], None] | None = None
) -> dict:
    chunks = split_words(text)
    if not chunks:
        raise ValueError("The transcript is empty.")

    summarizer = _get_summarizer()
    if progress_callback:
        progress_callback(
            f"Summarizing {len(chunks)} transcript section(s) with BART..."
        )
    chunk_summaries = _summarize_many(chunks, summarizer)
    reduced_summaries = chunk_summaries
    while len(reduced_summaries) > 1:
        reduction_chunks = split_words(
            " ".join(reduced_summaries), WORDS_PER_CHUNK
        )
        if len(reduction_chunks) >= len(reduced_summaries):
            break
        if progress_callback:
            progress_callback(
                f"Combining {len(reduced_summaries)} BART section summaries..."
            )
        next_summaries = _summarize_many(
            reduction_chunks,
            summarizer,
            max_length=160,
            min_length=35,
        )
        if sum(len(item.split()) for item in next_summaries) >= sum(
            len(item.split()) for item in reduced_summaries
        ):
            break
        reduced_summaries = next_summaries
    combined = " ".join(reduced_summaries)

    if _is_degenerate(combined):
        raise RuntimeError(
            "Couldn't generate a reliable summary from this transcript. "
            "Please try again or use a clearer transcript."
        )
    return {
        "summary": combined,
        "chunk_count": len(chunks),
        "chunk_summaries": chunk_summaries,
    }


def create_video_report(
    text: str,
    progress_callback: Callable[[str], None] | None = None,
    *,
    output_language: str = "en",
) -> dict:
    if output_language not in {"en", "hi"}:
        raise ValueError("Report language must be English or Hindi.")

    summary_data = summarize_long_text(text, progress_callback)
    key_points = _deduplicate_sentences(
        [
            sentence
            for chunk_summary in summary_data["chunk_summaries"]
            for sentence in _split_sentences(chunk_summary)
        ]
    )[:7]
    if not key_points or _is_degenerate(" ".join(key_points)):
        raise RuntimeError(
            "Couldn't generate a reliable summary from this transcript. "
            "Please try again or use a clearer transcript."
        )

    overview = _split_sentences(summary_data["summary"])
    tldr = _limit_words(" ".join(overview[:2] or key_points[:1]), 40)
    return {
        "tldr": tldr,
        "key_points": key_points,
        "overview": [summary_data["summary"]],
        "chunk_count": summary_data["chunk_count"],
        "chunk_summaries": summary_data["chunk_summaries"],
    }
