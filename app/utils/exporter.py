from __future__ import annotations
from pathlib import Path
from openpyxl import Workbook
from dataclasses import dataclass
from typing import List


@dataclass
class QARecord:
    number: int
    question: str
    answer_text: str
    verdict: str
    start_ms: int
    end_ms: int


def export_qa(records: List[QARecord], path: Path):
    wb = Workbook()
    ws = wb.active
    ws.title = "QA"
    ws.append(["#", "Вопрос", "Ответ (ASR)", "Итог", "Начало, мс", "Конец, мс"])
    for rec in records:
        ws.append([rec.number, rec.question, rec.answer_text, rec.verdict, rec.start_ms, rec.end_ms])
    wb.save(path)
