"""
Handles turning a YouTube URL into raw transcript text.

Primary path: youtube-transcript-api pulls existing captions (fast, free,
no audio download needed).

Fallback path: if no captions exist (disabled, auto-only in an unsupported
language, or the API errors out), we download just the audio with yt-dlp
and run it through Whisper locally.
"""
import os
import re
import tempfile
from dataclasses import dataclass

_YOUTUBE_ID_RE = re.compile(
    r"(?:youtu\.be/|youtube\.com/(?:watch\?v=|embed/|shorts/|live/))([A-Za-z0-9_-]{11})"
)

# Loaded lazily — only if we actually need the Whisper fallback, since
# loading the model is slow and most videos have captions already.
_whisper_model = None


@dataclass
class TranscriptResult:
    text: str
    source: str  # "captions" or "whisper"
    video_id: str


def extract_video_id(url_or_id: str) -> str:
    url_or_id = url_or_id.strip()
    match = _YOUTUBE_ID_RE.search(url_or_id)
    if match:
        return match.group(1)
    # Allow a bare video ID to be pasted directly.
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url_or_id):
        return url_or_id
    raise ValueError("Couldn't find a valid YouTube video ID in that link.")


def _fetch_captions(video_id: str) -> str | None:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import (
            NoTranscriptFound,
            TranscriptsDisabled,
            VideoUnavailable,
        )
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "The transcript pipeline requires 'youtube-transcript-api'. "
            "Install it with: pip install youtube-transcript-api"
        ) from exc

    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        # Prefer a manually created transcript, then fall back to any
        # auto-generated one, translating to English if needed.
        try:
            transcript = transcript_list.find_manually_created_transcript(
                ["en", "en-US", "en-GB"]
            )
        except NoTranscriptFound:
            transcript = transcript_list.find_generated_transcript(
                [t.language_code for t in transcript_list] or ["en"]
            )
        fetched = transcript.fetch()
        return " ".join(chunk["text"] for chunk in fetched if chunk["text"].strip())
    except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable):
        return None
    except Exception as e:
        print(f"[transcript_service] captions fetch failed for {video_id}: {e}")
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
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
    except Exception as e:
        # yt-dlp breaks whenever YouTube changes its page format faster
        # than a pinned yt-dlp version keeps up — this is the #1 cause of
        # a raw "Expecting value: line 1 column 1" JSON error surfacing
        # here. Re-raise with a message that actually says what to do.
        raise RuntimeError(
            "Couldn't download audio for this video (likely an outdated "
            "yt-dlp — run: pip install --upgrade yt-dlp). "
            f"Original error: {e}"
        ) from e
    return os.path.join(out_dir, f"{video_id}.mp3")


def _transcribe_with_whisper(audio_path: str) -> str:
    global _whisper_model
    try:
        import whisper
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "The Whisper fallback requires 'openai-whisper'. Install it with: "
            "pip install openai-whisper"
        ) from exc

    if _whisper_model is None:
        _whisper_model = whisper.load_model("base")
    result = _whisper_model.transcribe(audio_path)
    return result["text"].strip()


def get_transcript(url_or_id: str) -> TranscriptResult:
    video_id = extract_video_id(url_or_id)

    captions = _fetch_captions(video_id)
    if captions:
        return TranscriptResult(text=captions, source="captions", video_id=video_id)

    with tempfile.TemporaryDirectory() as tmp_dir:
        audio_path = _download_audio(video_id, tmp_dir)
        try:
            text = _transcribe_with_whisper(audio_path)
        except Exception as e:
            raise RuntimeError(f"Whisper transcription failed: {e}") from e

    if not text:
        raise RuntimeError(
            "Couldn't get a transcript from captions or Whisper for this video."
        )
    return TranscriptResult(text=text, source="whisper", video_id=video_id)