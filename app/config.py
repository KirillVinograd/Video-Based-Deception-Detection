from __future__ import annotations
import json
from dataclasses import dataclass, asdict
from pathlib import Path

DEFAULT_CONFIG = {
    "deception": {
        "threshold_hi": 0.65,
        "threshold_lo": 0.35,
        "window_seconds": 3.0,
    },
    "model": {
        "weights": [1.2, -0.8, 0.4],
        "bias": -0.1,
    },
    "recording": {
        "frame_rate": 15,
        "audio_rate": 16000,
    },
}


@dataclass
class AppConfig:
    threshold_hi: float
    threshold_lo: float
    window_seconds: float
    weights: list[float]
    bias: float
    frame_rate: int
    audio_rate: int

    @classmethod
    def load(cls, path: Path | None = None) -> "AppConfig":
        data = DEFAULT_CONFIG
        if path and path.exists():
            loaded = json.loads(path.read_text())
            # Deep merge simple dicts
            for key, value in loaded.items():
                if key in data and isinstance(data[key], dict) and isinstance(value, dict):
                    data[key].update(value)
                else:
                    data[key] = value
        dec = data["deception"]
        model = data["model"]
        rec = data.get("recording", {})
        return cls(
            threshold_hi=dec.get("threshold_hi", 0.65),
            threshold_lo=dec.get("threshold_lo", 0.35),
            window_seconds=dec.get("window_seconds", 3.0),
            weights=model.get("weights", [1.0, 1.0, 1.0]),
            bias=model.get("bias", 0.0),
            frame_rate=rec.get("frame_rate", 15),
            audio_rate=rec.get("audio_rate", 16000),
        )

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(DEFAULT_CONFIG | {
            "deception": {
                "threshold_hi": self.threshold_hi,
                "threshold_lo": self.threshold_lo,
                "window_seconds": self.window_seconds,
            },
            "model": {
                "weights": self.weights,
                "bias": self.bias,
            },
            "recording": {
                "frame_rate": self.frame_rate,
                "audio_rate": self.audio_rate,
            },
        }, indent=2))


def ensure_config(path: Path) -> AppConfig:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        AppConfig.load().save(path)
    return AppConfig.load(path)
