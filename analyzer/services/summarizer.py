"""
Chunk + summarize. Long transcripts (1hr+ videos) get split into
model-sized pieces, each summarized independently, then the partial
summaries are combined and summarized once more into a final summary.
This "map-reduce" approach keeps quality up without truncating content.
"""

import re
import json

_summarizer = None
MODEL_NAME = "facebook/bart-large-cnn"

# BART's practical input limit is ~1024 tokens; we chunk on words as a
# cheap proxy (~1 token ≈ 0.75 words for English) and stay well under it.
WORDS_PER_CHUNK = 350
REPORT_MODEL_NAME = "Qwen/Qwen2.5-0.5B-Instruct"
_report_model = None

_REPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "tldr": {"type": "string"},
        "key_points": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 4,
            "maxItems": 6,
        },
        "overview": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 2,
            "maxItems": 3,
        },
    },
    "required": ["tldr", "key_points", "overview"],
    "additionalProperties": False,
}


def _get_summarizer():
    global _summarizer
    if _summarizer is None:
        try:
            import torch
            from transformers import pipeline
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "The summarizer requires 'transformers' and 'torch'. "
                "Install them with: pip install transformers torch"
            ) from exc

        device = 0 if torch.cuda.is_available() else -1
        _summarizer = pipeline("summarization", model=MODEL_NAME, device=device)
    return _summarizer


def _get_report_model():
    global _report_model
    if _report_model is None:
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "The report generator requires 'transformers' and 'torch'. "
                "Install them with: pip install transformers torch"
            ) from exc

        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if device == "cuda" else torch.float32
        tokenizer = AutoTokenizer.from_pretrained(REPORT_MODEL_NAME)
        model = AutoModelForCausalLM.from_pretrained(
            REPORT_MODEL_NAME, torch_dtype=dtype
        ).to(device)
        _report_model = (model, tokenizer)
    return _report_model


def chunk_text(text: str, words_per_chunk: int = WORDS_PER_CHUNK) -> list[str]:
    words = text.split()
    if not words:
        return []
    return [
        " ".join(words[i : i + words_per_chunk])
        for i in range(0, len(words), words_per_chunk)
    ]


def _summarize_one(text: str, max_len: int = 220, min_len: int = 40) -> str:
    word_count = len(text.split())
    if word_count < 20:
        return text  # too short to meaningfully summarize
    # Keep the model's max/min sane relative to input length.
    max_len = min(max_len, max(min_len + 10, int(word_count * 0.8)))
    summarizer = _get_summarizer()
    result = summarizer(
        text, max_length=max_len, min_length=min(min_len, max_len - 5), do_sample=False
    )
    summary = result[0]["summary_text"].strip()
    if not re.search(r"[.!?][\"')\]]*$", summary):
        last_boundary = max(summary.rfind("."), summary.rfind("!"), summary.rfind("?"))
        if last_boundary > 0:
            summary = summary[: last_boundary + 1].rstrip()
    return summary


def summarize_long_text(text: str) -> dict:
    chunks = chunk_text(text)
    if not chunks:
        return {"summary": "", "chunk_count": 0, "chunk_summaries": []}

    chunk_summaries = [_summarize_one(c) for c in chunks]
    reduced_summaries = chunk_summaries
    while len(reduced_summaries) > 1:
        combined = " ".join(reduced_summaries)
        reduction_chunks = chunk_text(combined)
        next_summaries = [
            _summarize_one(chunk, max_len=320, min_len=60)
            for chunk in reduction_chunks
        ]
        if sum(len(item.split()) for item in next_summaries) >= len(combined.split()):
            break
        reduced_summaries = next_summaries

    final_summary = " ".join(reduced_summaries)

    return {
        "summary": final_summary,
        "chunk_count": len(chunks),
        "chunk_summaries": chunk_summaries,
    }


def _sentence_end(text: str) -> str:
    sentence = re.split(r"(?<=[.!?])\s+", text.strip(), maxsplit=1)[0]
    return sentence if sentence.endswith((".", "!", "?")) else sentence + "."


def _sample_ordered_sentences(sentences: list[str], limit: int) -> list[str]:
    if len(sentences) <= limit:
        return sentences
    indexes = [round(index * (len(sentences) - 1) / (limit - 1)) for index in range(limit)]
    return [sentences[index] for index in indexes]


def _evidence_supported(value: str, evidence: str) -> bool:
    stop_words = {
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
        "how", "in", "into", "is", "it", "of", "on", "or", "that", "the",
        "their", "this", "to", "was", "were", "what", "when", "which", "with",
    }
    evidence_words = set(re.findall(r"[a-z0-9]+", evidence.lower()))
    claim_words = set(re.findall(r"[a-z0-9]+", value.lower())) - stop_words
    return bool(claim_words) and claim_words <= evidence_words


def _fallback_report(summary_data: dict, source_text: str) -> dict:
    summary = summary_data["summary"].strip()
    summary_sentences = []
    for chunk_summary in summary_data["chunk_summaries"]:
        summary_sentences.extend(
            part.strip()
            for part in re.split(r"(?<=[.!?])\s+", chunk_summary)
            if len(part.split()) >= 6
        )
    unique_summary_sentences = list(dict.fromkeys(summary_sentences))
    source_sentences = [
        part.strip()
        for part in re.split(r"(?<=[.!?])\s+", source_text)
        if len(part.split()) >= 6
    ]
    source_sentences = list(dict.fromkeys(source_sentences))
    point_candidates = source_sentences or unique_summary_sentences
    key_points = _sample_ordered_sentences(point_candidates, 6)
    if len(key_points) < 4:
        for sentence in point_candidates:
            clauses = re.split(r"\s+(?:and|then|finally)\s+|,\s+", sentence)
            key_points.extend(
                clause.strip().rstrip(".,;:") + "."
                for clause in clauses
                if len(clause.split()) >= 4 and clause.strip() not in key_points
            )
            if len(key_points) >= 4:
                break
        key_points = key_points[:6]
    if not key_points:
        key_points = [_sentence_end(summary)]

    overview_sentences = _sample_ordered_sentences(
        source_sentences or unique_summary_sentences, 6
    )
    if not overview_sentences:
        overview_sentences = [_sentence_end(summary)]
    midpoint = max(1, (len(overview_sentences) + 1) // 2)
    overview = [
        " ".join(overview_sentences[:midpoint]),
        " ".join(overview_sentences[midpoint:]) or overview_sentences[-1],
    ]
    tldr_candidates = unique_summary_sentences
    if len(tldr_candidates) < 2:
        tldr_candidates = source_sentences or [_sentence_end(summary)]
    tldr_parts = _sample_ordered_sentences(tldr_candidates, 3)
    tldr = "; ".join(part.rstrip(".!? ") for part in tldr_parts) + "."
    return {
        "tldr": tldr,
        "key_points": key_points,
        "overview": overview,
    }


def create_video_report(text: str) -> dict:
    summary_data = summarize_long_text(text)
    evidence = " ".join(summary_data["chunk_summaries"])
    grounding_text = f"{text} {evidence}"
    try:
        import torch
        from lmformatenforcer import JsonSchemaParser
        from lmformatenforcer.integrations.transformers import (
            build_transformers_prefix_allowed_tokens_fn,
        )

        model, tokenizer = _get_report_model()
        messages = [
            {
                "role": "system",
                "content": (
                    "Write a faithful report using only facts in the source. "
                    "Do not add advice, examples, or claims. TLDR is one sentence. "
                    "Key points are distinct and concise. Overview contains two "
                    "short paragraphs describing events in their original order."
                ),
            },
            {"role": "user", "content": f"Source transcript summary:\n{evidence}"},
        ]
        input_ids = tokenizer.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True, return_tensors="pt"
        ).to(model.device)
        allowed_tokens = build_transformers_prefix_allowed_tokens_fn(
            tokenizer, JsonSchemaParser(_REPORT_SCHEMA)
        )
        with torch.inference_mode():
            output = model.generate(
                input_ids,
                attention_mask=torch.ones_like(input_ids),
                max_new_tokens=420,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
                prefix_allowed_tokens_fn=allowed_tokens,
            )
        generated = tokenizer.decode(
            output[0][input_ids.shape[1] :], skip_special_tokens=True
        )
        report = json.loads(generated)
        if not all(
            _evidence_supported(value, grounding_text)
            for value in [report["tldr"], *report["key_points"], *report["overview"]]
        ):
            report = _fallback_report(summary_data, text)
    except Exception:
        report = _fallback_report(summary_data, text)

    report["tldr"] = _sentence_end(report["tldr"])
    report["key_points"] = report["key_points"][:6]
    report["overview"] = report["overview"][:3]
    return {
        **report,
        "chunk_count": summary_data["chunk_count"],
        "chunk_summaries": summary_data["chunk_summaries"],
    }