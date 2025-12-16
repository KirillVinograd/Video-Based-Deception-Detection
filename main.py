from __future__ import annotations
import sys
from pathlib import Path
import logging
from datetime import datetime

from PySide6 import QtWidgets

from app.config import ensure_config
from app.storage import Storage
from app.ui.user_selection import UserSelection
from app.ui.session_window import SessionWindow
from app.ui.review_window import ReviewWindow
from app.utils.exporter import QARecord


class MainApp(QtWidgets.QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.setApplicationName("Thermo Deception Detector")
        log_path = Path.home() / ".thermodeception" / "diagnostics.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(level=logging.INFO, filename=log_path, filemode="a", format="%(asctime)s %(levelname)s %(message)s")
        self.config = ensure_config(Path.home() / ".thermodeception" / "config.json")
        self.storage = Storage(Path.home() / ".thermodeception" / "session.sqlite")
        self.user = None
        self.session_win = None
        self.review_win = None
        self._select_user()

    def _select_user(self):
        dialog = QtWidgets.QDialog()
        selector = UserSelection(self.storage)
        layout = QtWidgets.QVBoxLayout(dialog)
        layout.addWidget(selector)
        dialog.setWindowTitle("Выбор пользователя")
        dialog.exec()
        self.user = selector.selected_user
        if not self.user:
            sys.exit(0)
        self._open_session()

    def _open_session(self):
        self.session_win = SessionWindow(self.storage, self.user, self.config, Path("sample/sample.mp4"))
        self.session_win.recording_stopped.connect(self._on_recording_finished)
        self.session_win.show()

    def _on_recording_finished(self, folder: Path, timeline):
        if not folder:
            return
        # finalize stub QA rows
        records = []
        for idx in range(self.session_win.questions_table.rowCount()):
            question = self.session_win.questions_table.item(idx, 0).text()
            records.append(
                {
                    "number": idx + 1,
                    "question": question,
                    "answer_text": "(ASR черновик)",
                    "verdict": timeline[-1].label if timeline else "Правда",
                    "start_ms": timeline[0].timestamp_ms if timeline else 0,
                    "end_ms": timeline[-1].timestamp_ms if timeline else 0,
                }
            )
        qa_records = [
            QARecord(
                number=rec["number"],
                question=rec["question"],
                answer_text=rec["answer_text"],
                verdict=rec["verdict"],
                start_ms=rec["start_ms"],
                end_ms=rec["end_ms"],
            )
            for rec in records
        ]
        review = ReviewWindow(folder, timeline)
        review.load_records(qa_records)
        review.show()
        self.review_win = review


def main():
    app = MainApp(sys.argv)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
