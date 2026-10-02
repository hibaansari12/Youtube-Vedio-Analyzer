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
import shutil
import subprocess
import sys
import tempfile
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
from dataclasses import dataclass, field

_YOUTUBE_ID_RE = re.compile(
    r"(?:youtu\.be/|youtube\.com/(?:watch\?v=|embed/|shorts/|live/))([A-Za-z0-9_-]{11})"
)

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


@dataclass
class TranscriptResult:
    text: str
    source: str
    video_id: str
    segments: list[dict[str, float | str]] = field(default_factory=list)


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
        with urlopen(endpoint, timeout=5) as response:
            metadata = json.load(response)
        title = metadata.get("title")
        return title.strip() if isinstance(title, str) and title.strip() else None
    except Exception:
        return None


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
                "when YouTube blocks the current session or restricts the video. "
                "If you are signed in to YouTube in a supported browser, set "
                "YTDLP_COOKIES_FROM_BROWSER to that browser name and restart the "
                "app. Otherwise, paste the transcript directly. "
                f"yt-dlp {yt_dlp.version.__version__} reported: {detail}"
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

    captions = _fetch_captions(video_id)
    if captions:
        return TranscriptResult(text=captions, source="captions", video_id=video_id)

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