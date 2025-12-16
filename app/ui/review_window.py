from __future__ import annotations
from pathlib import Path
from typing import List
from PySide6 import QtCore, QtWidgets

from app.utils.exporter import QARecord, export_qa
from app.utils.timeline import TimelineEntry


class ReviewWindow(QtWidgets.QWidget):
    def __init__(self, session_folder: Path, timeline: List[TimelineEntry]):
        super().__init__()
        self.session_folder = session_folder
        self.timeline = timeline
        self.setWindowTitle("Разбор сессии")
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(QtWidgets.QLabel("Разбор: синхронное воспроизведение аудио/видео упрощено в этой версии. Откройте файл thermal_view.mp4 и audio.wav в плеере."))
        self.table = QtWidgets.QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["#", "Вопрос", "Ответ (ASR)", "Итог", "Начало", "Конец"])
        layout.addWidget(self.table)
        btn_layout = QtWidgets.QHBoxLayout()
        self.export_btn = QtWidgets.QPushButton("Экспорт в Excel")
        self.open_folder_btn = QtWidgets.QPushButton("Открыть папку сессии")
        btn_layout.addWidget(self.export_btn)
        btn_layout.addWidget(self.open_folder_btn)
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        self.export_btn.clicked.connect(self._export)
        self.open_folder_btn.clicked.connect(self._open_folder)

    def load_records(self, records: List[QARecord]):
        self.table.setRowCount(0)
        for rec in records:
            row = self.table.rowCount()
            self.table.insertRow(row)
            for col, val in enumerate([rec.number, rec.question, rec.answer_text, rec.verdict, rec.start_ms, rec.end_ms]):
                item = QtWidgets.QTableWidgetItem(str(val))
                self.table.setItem(row, col, item)
        self.records = records

    def _export(self):
        if not hasattr(self, 'records'):
            QtWidgets.QMessageBox.warning(self, "Нет данных", "Нет строк для экспорта")
            return
        path = self.session_folder / "qa.xlsx"
        export_qa(self.records, path)
        QtWidgets.QMessageBox.information(self, "Экспорт", f"Сохранено: {path}")

    def _open_folder(self):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(self.session_folder)))


from PySide6 import QtGui  # placed last
