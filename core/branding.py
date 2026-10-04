from base64 import b64encode
from pathlib import Path

_LOGO_PATH = Path(__file__).resolve().parents[1] / "assets" / "video-analyzer-mark.svg"


def logo_data_uri() -> str:
    svg_data = b64encode(_LOGO_PATH.read_bytes()).decode("ascii")
    return f"data:image/svg+xml;base64,{svg_data}"
