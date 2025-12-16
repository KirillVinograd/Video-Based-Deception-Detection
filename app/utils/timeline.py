from __future__ import annotations
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List


@dataclass
class TimelineEntry:
    timestamp_ms: int
    label: str
    score: float


@dataclass
class SegmentEntry:
    type: str
    start_ms: int
    end_ms: int | None
    label: str | None
    question_text: str | None
    notes: str | None = None


def save_timeline(entries: List[TimelineEntry], path: Path):
    data = [asdict(e) for e in entries]
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def save_segments(entries: List[SegmentEntry], path: Path):
    data = [asdict(e) for e in entries]
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
