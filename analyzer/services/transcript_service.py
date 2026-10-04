"""
Handles turning a YouTube URL into raw transcript text.

Primary path:
  1. youtube-transcript-api pulls existing captions (fast, free, no audio download needed).
  2. yt-dlp direct subtitle extraction (fast JSON3/VTT parser, bypasses YouTube media stream 403 blocks).

Fallback path:
  3. If no captions exist anywhere, downloads audio with yt-dlp (emulating mobile/android client to prevent 403)
     and transcribes with Whisper locally.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import json
import logging
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen, Request
from dataclasses import dataclass, field

_YOUTUBE_ID_RE = re.compile(
    r"(?:youtu\.be/|youtube\.com/(?:watch\?v=|embed/|shorts/|live/))([A-Za-z0-9_-]{11})"
)

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")
_PREFERRED_TRANSCRIPT_LANGUAGES = ["en", "en-US", "en-GB", "hi"]
_logger = logging.getLogger(__name__)


class _YtDlpLogger:
    def debug(self, message: str) -> None:
        _logger.debug("%s", message)

    def warning(self, message: str) -> None:
        _logger.debug("%s", message)

    def error(self, message: str) -> None:
        _logger.debug("%s", message)


@dataclass
class TranscriptResult:
    text: str
    source: str
    video_id: str
    segments: list[dict[str, float | str]] = field(default_factory=list)


def _dedupe_consecutive_caption_segments(
    segments: list[dict[str, float | str]],
) -> list[dict[str, float | str]]:
    """Drop only adjacent captions that repeat the exact same text."""
    deduplicated = []
    previous_text = None
    for segment in segments:
        text = segment.get("text")
        if not isinstance(text, str):
            continue
        normalized = re.sub(r"\W+", "", text.casefold(), flags=re.UNICODE)
        if not normalized or normalized == previous_text:
            continue
        deduplicated.append(segment)
        previous_text = normalized
    return deduplicated


def clean_transcript(text: str) -> str:
    """Remove common speech fillers and caption artifacts without changing meaning."""
    text = re.sub(r">{2,}", " ", text)
    filler_pattern = r"\b(?:uh+|um+|erm+|er+)\b(?!-)"
    text = re.sub(
        rf"(?<=\w)(?:,\s*|\s+){filler_pattern}[,،]?\s*",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        rf"(?<!\w){filler_pattern}[,،]?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"[ \t]+([,.;:!?])", r"\1", text)
    text = re.sub(r"([,;:!?])(?=\S)", r"\1 ", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def format_transcript_download(
    title: str,
    text: str,
    segments: list[dict[str, float | str]],
) -> str:
    """Format a transcript as readable, timestamped paragraphs for text download."""
    lines = [title.strip() or "Video transcript", "=" * 72, ""]
    if segments:
        paragraph_start: float | None = None
        paragraph_parts: list[str] = []
        paragraph_words = 0

        def flush_paragraph() -> None:
            if paragraph_start is None or not paragraph_parts:
                return
            timestamp = int(paragraph_start)
            hours, remainder = divmod(timestamp, 3600)
            minutes, seconds = divmod(remainder, 60)
            label = (
                f"{hours:02}:{minutes:02}:{seconds:02}"
                if hours
                else f"{minutes:02}:{seconds:02}"
            )
            lines.append(f"[{label}] {' '.join(paragraph_parts)}")
            lines.append("")

        for segment in segments:
            segment_text = segment.get("text")
            if not isinstance(segment_text, str):
                continue
            cleaned = clean_transcript(segment_text)
            if not cleaned:
                continue

            start = segment.get("start", 0.0)
            segment_start = float(start) if isinstance(start, (int, float)) else 0.0
            if paragraph_start is not None and (
                segment_start - paragraph_start >= 30 or paragraph_words >= 70
            ):
                flush_paragraph()
                paragraph_parts = []
                paragraph_words = 0
                paragraph_start = None
            if paragraph_start is None:
                paragraph_start = segment_start
            paragraph_parts.append(cleaned)
            paragraph_words += len(cleaned.split())
        flush_paragraph()
    else:
        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?।])\s+", clean_transcript(text))
            if sentence.strip()
        ]
        paragraph: list[str] = []
        word_count = 0
        for sentence in sentences:
            sentence_words = len(sentence.split())
            if paragraph and word_count + sentence_words > 80:
                lines.append(" ".join(paragraph))
                lines.append("")
                paragraph = []
                word_count = 0
            paragraph.append(sentence)
            word_count += sentence_words
        if paragraph:
            lines.append(" ".join(paragraph))

    return "\n".join(lines).rstrip() + "\n"


def extract_video_id(url_or_id: str) -> str:
    url_or_id = url_or_id.strip()
    match = _YOUTUBE_ID_RE.search(url_or_id)
    if match:
        return match.group(1)
    # Allow a bare video ID to be pasted directly.
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url_or_id):
        return url_or_id
    raise ValueError("Couldn't find a valid YouTube video ID in that link.")


def get_video_title(url_or_id: str) -> str | None:
    video_id = extract_video_id(url_or_id)
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    endpoint = "https://www.youtube.com/oembed?" + urlencode(
        {"url": video_url, "format": "json"}
    )
    try:
        req = Request(endpoint, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urlopen(req, timeout=5) as response:
            metadata = json.load(response)
        title = metadata.get("title")
        return title.strip() if isinstance(title, str) and title.strip() else None
    except Exception:
        return None


def _fetch_captions_api(video_id: str) -> tuple[str, list[dict[str, float | str]]] | None:
    """Fetch captions using youtube-transcript-api (supports both 1.x and 0.6.x)."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ModuleNotFoundError:
        return None

    try:
        # Check if v1.x instance API is available
        if hasattr(YouTubeTranscriptApi, "fetch") and callable(getattr(YouTubeTranscriptApi, "fetch", None)):
            try:
                api = YouTubeTranscriptApi()
                transcript_list = api.list(video_id)
                available_languages = {
                    transcript.language_code for transcript in transcript_list
                }
                selected_language = next(
                    (
                        language
                        for language in _PREFERRED_TRANSCRIPT_LANGUAGES
                        if language in available_languages
                    ),
                    None,
                )
                if selected_language:
                    fetched = transcript_list.find_transcript(
                        [selected_language]
                    ).fetch()
                    segments = []
                    words = []
                    for chunk in fetched:
                        txt = getattr(chunk, "text", "") or ""
                        txt = txt.strip()
                        if txt:
                            start_time = float(getattr(chunk, "start", 0.0))
                            dur_time = float(getattr(chunk, "duration", 0.0))
                            segments.append({
                                "start": round(start_time, 2),
                                "end": round(start_time + dur_time, 2),
                                "text": txt,
                            })
                            words.append(txt)
                    if words:
                        segments = _dedupe_consecutive_caption_segments(segments)
                        return " ".join(
                            str(segment["text"]) for segment in segments
                        ), segments
            except Exception as exc:
                _logger.debug(
                    "Caption API lookup failed for %s: %s", video_id, exc
                )

        # Check legacy get_transcript
        if hasattr(YouTubeTranscriptApi, "get_transcript"):
            fetched = YouTubeTranscriptApi.get_transcript(
                video_id, languages=_PREFERRED_TRANSCRIPT_LANGUAGES
            )
            segments = []
            words = []
            for chunk in fetched:
                txt = chunk.get("text", "").strip()
                if txt:
                    start_time = float(chunk.get("start", 0.0))
                    dur_time = float(chunk.get("duration", 0.0))
                    segments.append({
                        "start": round(start_time, 2),
                        "end": round(start_time + dur_time, 2),
                        "text": txt,
                    })
                    words.append(txt)
            if words:
                segments = _dedupe_consecutive_caption_segments(segments)
                return " ".join(
                    str(segment["text"]) for segment in segments
                ), segments
    except Exception as e:
        _logger.debug("Legacy caption API lookup failed for %s: %s", video_id, e)

    return None


def _fetch_captions_ytdlp(video_id: str) -> tuple[str, list[dict[str, float | str]], str] | None:
    """Fetch captions via yt-dlp metadata without downloading audio/video (bypasses 403 blocks)."""
    try:
        import yt_dlp
    except ModuleNotFoundError:
        return None

    ydl_opts = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "logger": _YtDlpLogger(),
        "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
    }
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            subtitles = info.get("subtitles") or {}
            auto_captions = info.get("automatic_captions") or {}

            chosen_format = None
            source_label = "captions"

            for pool, label in [(subtitles, "captions"), (auto_captions, "auto-captions")]:
                available_langs = list(pool.keys())
                matched_lang = None
                for pref in _PREFERRED_TRANSCRIPT_LANGUAGES:
                    if pref in available_langs:
                        matched_lang = pref
                        break

                if matched_lang:
                    formats = pool[matched_lang]
                    chosen_format = next(
                        (f for f in formats if f.get("ext") == "json3"),
                        formats[0] if formats else None,
                    )
                    if chosen_format:
                        source_label = label
                        break

            if not chosen_format or "url" not in chosen_format:
                return None

            req = Request(
                chosen_format["url"],
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            )
            with urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
                data = json.loads(raw)
                events = data.get("events", [])
                segments = []
                words = []
                for ev in events:
                    segs = ev.get("segs", [])
                    line = "".join(s.get("utf8", "") for s in segs).strip()
                    if line and line != "\n":
                        t_start = ev.get("tStartMs", 0) / 1000.0
                        t_dur = ev.get("dDurationMs", 0) / 1000.0
                        segments.append({
                            "start": round(t_start, 2),
                            "end": round(t_start + t_dur, 2),
                            "text": line,
                        })
                        words.append(line)
                if words:
                    segments = _dedupe_consecutive_caption_segments(segments)
                    return (
                        " ".join(str(segment["text"]) for segment in segments),
                        segments,
                        source_label,
                    )
    except Exception as e:
        _logger.debug("yt-dlp caption lookup failed for %s: %s", video_id, e)

    return None


def _download_audio(video_id: str, out_dir: str) -> str:
    try:
        import yt_dlp
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "The Whisper fallback requires 'yt-dlp'. Install it with: "
            "pip install yt-dlp"
        ) from exc

    out_path = os.path.join(out_dir, f"{video_id}.%(ext)s")
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": out_path,
        "quiet": True,
        "noplaylist": True,
        "logger": _YtDlpLogger(),
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios", "web"]
            }
        },
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }
    deno_path = shutil.which("deno")
    if not deno_path:
        winget_packages = (
            Path(os.environ.get("LOCALAPPDATA", ""))
            / "Microsoft"
            / "WinGet"
            / "Packages"
        )
        deno_executables = sorted(
            winget_packages.glob("DenoLand.Deno_*/deno.exe"), reverse=True
        )
        if deno_executables:
            deno_path = str(deno_executables[0])
    if deno_path:
        ydl_opts["js_runtimes"] = {"deno": {"path": deno_path}}

    cookie_browser = os.environ.get("YTDLP_COOKIES_FROM_BROWSER", "").strip().lower()
    if cookie_browser:
        supported_browsers = {"brave", "chrome", "chromium", "edge", "firefox", "opera", "vivaldi"}
        if cookie_browser not in supported_browsers:
            raise RuntimeError(
                "YTDLP_COOKIES_FROM_BROWSER must be a supported browser name "
                "such as chrome, edge, firefox, or brave."
            )
        ydl_opts["cookiesfrombrowser"] = (cookie_browser,)
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
    except Exception as e:
        detail = _ANSI_ESCAPE_RE.sub("", str(e))
        if "403" in detail or "forbidden" in detail.lower():
            raise RuntimeError(
                "YouTube refused the audio download (HTTP 403). This can happen "
                "when YouTube blocks automated audio streaming. "
                "Try another video with captions available, or try again later. "
                f"(Detail: {detail})"
            ) from e
        raise RuntimeError(
            f"Couldn't download audio for this video: {detail}"
        ) from e
    return os.path.join(out_dir, f"{video_id}.mp3")


def _transcribe_with_faster_whisper(
    audio_path: str,
) -> tuple[str, list[dict[str, float | str]]]:
    worker = subprocess.run(
        [sys.executable, "-m", "analyzer.services.whisper_worker", audio_path],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if worker.returncode:
        detail = (worker.stderr or worker.stdout).strip()[-4000:]
        raise RuntimeError(detail or f"ASR worker exited with code {worker.returncode}")

    try:
        result = json.loads(worker.stdout)
        transcript = result["text"]
        segments = result["segments"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise RuntimeError("ASR worker returned an invalid result.") from exc
    return transcript, segments


def get_transcript(url_or_id: str) -> TranscriptResult:
    video_id = extract_video_id(url_or_id)

    # 1. Try youtube-transcript-api
    api_result = _fetch_captions_api(video_id)
    if api_result:
        text, segments = api_result
        if text.strip():
            return TranscriptResult(
                text=text, source="captions", video_id=video_id, segments=segments
            )

    # 2. Try yt-dlp direct subtitle extraction (no audio download)
    ytdlp_result = _fetch_captions_ytdlp(video_id)
    if ytdlp_result:
        text, segments, source_label = ytdlp_result
        if text.strip():
            return TranscriptResult(
                text=text, source=source_label, video_id=video_id, segments=segments
            )

    # 3. Fallback: Download audio and run faster-whisper
    with tempfile.TemporaryDirectory() as tmp_dir:
        audio_path = _download_audio(video_id, tmp_dir)
        try:
            text, segments = _transcribe_with_faster_whisper(audio_path)
        except Exception as e:
            raise RuntimeError(f"faster-whisper transcription failed: {e}") from e

    if not text:
        raise RuntimeError(
            "Couldn't get a transcript from captions or Whisper for this video."
        )
    return TranscriptResult(
        text=text, source="faster-whisper", video_id=video_id, segments=segments
    )