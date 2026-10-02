"""Run faster-whisper in an isolated process to avoid OpenMP DLL conflicts."""

import json
import os
import sys
from pathlib import Path


def main() -> None:
    torch_lib = Path(sys.prefix) / "Lib" / "site-packages" / "torch" / "lib"
    if os.name == "nt" and torch_lib.is_dir():
        os.environ["PATH"] = f"{torch_lib}{os.pathsep}{os.environ.get('PATH', '')}"
        dll_directory = os.add_dll_directory(str(torch_lib))

    try:
        import ctranslate2
        from faster_whisper import WhisperModel
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "The audio fallback requires faster-whisper. Install it with: "
            "pip install -r requirements.txt"
        ) from exc

    use_cuda = ctranslate2.get_cuda_device_count() > 0
    model = WhisperModel(
        "large-v3",
        device="cuda" if use_cuda else "cpu",
        compute_type="float16" if use_cuda else "int8",
    )
    segments, _ = model.transcribe(sys.argv[1], vad_filter=True)
    timestamped_segments = [
        {
            "start": float(segment.start),
            "end": float(segment.end),
            "text": segment.text.strip(),
        }
        for segment in segments
        if segment.text.strip()
    ]
    print(
        json.dumps(
            {
                "text": " ".join(segment["text"] for segment in timestamped_segments),
                "segments": timestamped_segments,
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()