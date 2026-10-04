"""Local English/Hindi translation for transcripts and report text."""

import re
from collections.abc import Callable

_MODEL_NAMES = {
    ("en", "hi"): "Helsinki-NLP/opus-mt-en-hi",
    ("hi", "en"): "Helsinki-NLP/opus-mt-hi-en",
}
_MAX_INPUT_TOKENS = 450
_BATCH_SIZE = 4
_translators = {}


def detect_transcript_language(text: str) -> str:
    """Detect Hindi written in Devanagari; otherwise assume English."""
    devanagari_count = sum("\u0900" <= char <= "\u097f" for char in text)
    letter_count = sum(char.isalpha() for char in text)
    return "hi" if devanagari_count >= max(5, letter_count * 0.2) else "en"


def _get_translator(source_language: str, target_language: str):
    model_name = _MODEL_NAMES.get((source_language, target_language))
    if model_name is None:
        raise ValueError("Translation supports English and Hindi only.")

    key = (source_language, target_language)
    if key not in _translators:
        try:
            import torch
            from transformers import MarianMTModel, MarianTokenizer
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Hindi translation requires 'transformers', 'torch', and "
                "'sentencepiece'. Install them with: pip install -r requirements.txt"
            ) from exc

        tokenizer = MarianTokenizer.from_pretrained(
            model_name, clean_up_tokenization_spaces=True
        )
        model = MarianMTModel.from_pretrained(model_name)
        if torch.cuda.is_available():
            model = model.to("cuda")
        _translators[key] = (model, tokenizer, torch)
    return _translators[key]


def _token_count(text: str, tokenizer) -> int:
    return len(tokenizer.encode(text, add_special_tokens=False))


def _split_long_unit(unit: str, tokenizer) -> list[str]:
    if _token_count(unit, tokenizer) <= _MAX_INPUT_TOKENS:
        return [unit]

    words = unit.split()
    if len(words) > 1:
        pieces = []
        current = []
        for word in words:
            candidate = " ".join([*current, word])
            if current and _token_count(candidate, tokenizer) > _MAX_INPUT_TOKENS:
                pieces.append(" ".join(current))
                current = [word]
            else:
                current.append(word)
        if current:
            pieces.append(" ".join(current))
        return pieces

    token_ids = tokenizer.encode(unit, add_special_tokens=False)
    return [
        tokenizer.decode(
            token_ids[index : index + _MAX_INPUT_TOKENS],
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )
        for index in range(0, len(token_ids), _MAX_INPUT_TOKENS)
    ]


def _split_translation_chunks(text: str, tokenizer) -> list[str]:
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?।])\s+|\n+", text.strip())
        if sentence.strip()
    ]
    chunks = []
    current = []

    for sentence in sentences:
        for unit in _split_long_unit(sentence, tokenizer):
            candidate = " ".join([*current, unit])
            if current and _token_count(candidate, tokenizer) > _MAX_INPUT_TOKENS:
                chunks.append(" ".join(current))
                current = [unit]
            else:
                current.append(unit)
        if current and _token_count(" ".join(current), tokenizer) >= _MAX_INPUT_TOKENS:
            chunks.append(" ".join(current))
            current = []

    if current:
        chunks.append(" ".join(current))
    return chunks


def translate_texts(
    texts: list[str],
    source_language: str,
    target_language: str,
    progress_callback: Callable[[str], None] | None = None,
) -> list[str]:
    """Translate strings locally while preserving their order and boundaries."""
    if source_language == target_language:
        return list(texts)
    if (source_language, target_language) not in _MODEL_NAMES:
        raise ValueError("Translation supports English and Hindi only.")

    nonempty_indexes = [index for index, text in enumerate(texts) if text.strip()]
    results = ["" for _ in texts]
    if not nonempty_indexes:
        return results

    if progress_callback:
        progress_callback(
            f"Loading the local {source_language}-to-{target_language} translator..."
        )
    model, tokenizer, torch = _get_translator(source_language, target_language)
    chunks_by_text = {
        index: _split_translation_chunks(texts[index], tokenizer)
        for index in nonempty_indexes
    }
    pending = [
        (index, chunk)
        for index in nonempty_indexes
        for chunk in chunks_by_text[index]
    ]
    translated_by_text = {index: [] for index in nonempty_indexes}

    batch_count = (len(pending) + _BATCH_SIZE - 1) // _BATCH_SIZE
    for start in range(0, len(pending), _BATCH_SIZE):
        batch = pending[start : start + _BATCH_SIZE]
        if progress_callback:
            progress_callback(
                f"Translating batch {start // _BATCH_SIZE + 1}/{batch_count}..."
            )
        inputs = tokenizer(
            [chunk for _, chunk in batch],
            return_tensors="pt",
            padding=True,
            truncation=False,
        )
        inputs = inputs.to(model.device)
        with torch.inference_mode():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=_MAX_INPUT_TOKENS,
                num_beams=2,
                do_sample=False,
            )
        translated_chunks = tokenizer.batch_decode(
            output_ids,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=True,
        )
        for (text_index, _), translated in zip(batch, translated_chunks):
            translated_by_text[text_index].append(translated.strip())

    for index, translated_chunks in translated_by_text.items():
        results[index] = " ".join(chunk for chunk in translated_chunks if chunk)
    return results


def translate_text(
    text: str,
    source_language: str,
    target_language: str,
    progress_callback: Callable[[str], None] | None = None,
) -> str:
    """Translate one string locally without truncating long input."""
    return translate_texts(
        [text], source_language, target_language, progress_callback
    )[0]
