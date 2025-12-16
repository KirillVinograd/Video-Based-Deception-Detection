from __future__ import annotations
import json
import subprocess
import time
from pathlib import Path
from typing import List

import cv2
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from app.config import AppConfig
from app.services.audio import AudioRecorder
from app.services.deception import DeceptionService
from app.services.thermal_adapters import DummyThermalAdapter, FileThermalAdapter, ThermalAdapter, ThermalFrame
from app.storage import Storage, User
from app.utils.timeline import TimelineEntry, save_timeline
from app.utils.exporter import export_qa, QARecord


class FrameWorker(QtCore.QThread):
    frame_captured = QtCore.Signal(np.ndarray, int, str, float)
    error = QtCore.Signal(str)

    def __init__(self, adapter: ThermalAdapter, deception: DeceptionService, frame_rate: int = 15):
        super().__init__()
        self.adapter = adapter
        self.deception = deception
        self.frame_rate = frame_rate
        self._running = False
        self._last_frame = None
        self.timeline: List[TimelineEntry] = []

    def run(self):
        self._running = True
        interval = 1.0 / self.frame_rate
        while self._running:
            try:
                frame = self.adapter.read_frame()
                ts_ms = int(time.monotonic() * 1000)
                label, score = self.deception.infer(frame, ts_ms)
                self.timeline.append(TimelineEntry(timestamp_ms=ts_ms, label=label, score=score))
                self._last_frame = frame.frame
                self.frame_captured.emit(frame.frame, ts_ms, label, score)
                time.sleep(interval)
            except Exception as exc:
                self.error.emit(str(exc))
                break

    def stop(self):
        self._running = False


class SessionWindow(QtWidgets.QWidget):
    recording_stopped = QtCore.Signal(Path, List[TimelineEntry])

    def __init__(self, storage: Storage, user: User, config: AppConfig, file_adapter_path: Path):
        super().__init__()
        self.storage = storage
        self.user = user
        self.config = config
        self.file_adapter_path = file_adapter_path

        self.setWindowTitle(f"Сессия: {user.full_name}")
        self.adapter: ThermalAdapter | None = None
        self.frame_worker: FrameWorker | None = None
        self.audio_recorder = AudioRecorder(samplerate=config.audio_rate)
        self.session_folder: Path | None = None
        self.qa_records: List[QARecord] = []
        self.video_writer = None

        self._build_ui()
        self._setup_connections()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout()

        device_layout = QtWidgets.QHBoxLayout()
        self.thermal_combo = QtWidgets.QComboBox()
        self.thermal_combo.addItems(["Dummy (webcam)", "Файл (sample/sample.mp4)"])
        self.thermal_check = QtWidgets.QPushButton("Проверить")
        self.instruction_btn = QtWidgets.QPushButton("Инструкция")
        device_layout.addWidget(QtWidgets.QLabel("Тепловизор"))
        device_layout.addWidget(self.thermal_combo)
        device_layout.addWidget(self.thermal_check)
        device_layout.addWidget(self.instruction_btn)

        audio_layout = QtWidgets.QHBoxLayout()
        self.audio_combo = QtWidgets.QComboBox()
        try:
            for dev in self.audio_recorder.list_devices():
                self.audio_combo.addItem(dev.name, dev.index)
        except Exception:
            self.audio_combo.addItem("По умолчанию", None)
        self.audio_check = QtWidgets.QPushButton("Проверить 5 секунд")
        self.audio_level = QtWidgets.QProgressBar()
        self.audio_level.setRange(0, 100)
        audio_layout.addWidget(QtWidgets.QLabel("Микрофон"))
        audio_layout.addWidget(self.audio_combo)
        audio_layout.addWidget(self.audio_check)
        audio_layout.addWidget(self.audio_level)

        folder_layout = QtWidgets.QHBoxLayout()
        self.folder_edit = QtWidgets.QLineEdit()
        self.folder_btn = QtWidgets.QPushButton("Выбрать папку")
        folder_layout.addWidget(QtWidgets.QLabel("Папка сессии"))
        folder_layout.addWidget(self.folder_edit)
        folder_layout.addWidget(self.folder_btn)

        questions_layout = QtWidgets.QHBoxLayout()
        self.questions_table = QtWidgets.QTableWidget(0, 1)
        self.questions_table.setHorizontalHeaderLabels(["Вопрос"])
        self.add_question_btn = QtWidgets.QPushButton("Добавить")
        self.remove_question_btn = QtWidgets.QPushButton("Удалить")
        self.import_btn = QtWidgets.QPushButton("Импорт txt/xlsx")
        q_buttons = QtWidgets.QVBoxLayout()
        q_buttons.addWidget(self.add_question_btn)
        q_buttons.addWidget(self.remove_question_btn)
        q_buttons.addWidget(self.import_btn)
        questions_layout.addWidget(self.questions_table)
        questions_layout.addLayout(q_buttons)

        live_layout = QtWidgets.QHBoxLayout()
        self.preview = QtWidgets.QLabel()
        self.preview.setFixedSize(480, 320)
        self.preview.setStyleSheet("background:#111;")
        right_layout = QtWidgets.QVBoxLayout()
        self.rec_btn = QtWidgets.QPushButton("Начать запись")
        self.rec_indicator = QtWidgets.QLabel("REC ●")
        self.rec_indicator.setStyleSheet("color: red; font-weight: bold;")
        self.rec_indicator.hide()
        self.timer_label = QtWidgets.QLabel("00:00")
        self.truth_label = QtWidgets.QLabel("—")
        self.truth_label.setAlignment(QtCore.Qt.AlignCenter)
        self.truth_label.setStyleSheet("font-size:32px; border:1px solid #444; padding:8px;")
        self.next_question_btn = QtWidgets.QPushButton("Следующий вопрос")
        self.answer_end_btn = QtWidgets.QPushButton("Конец ответа")
        self.event_btn = QtWidgets.QPushButton("Метка события")
        right_layout.addWidget(self.rec_btn)
        right_layout.addWidget(self.rec_indicator)
        right_layout.addWidget(self.timer_label)
        right_layout.addWidget(self.truth_label)
        right_layout.addWidget(self.next_question_btn)
        right_layout.addWidget(self.answer_end_btn)
        right_layout.addWidget(self.event_btn)
        live_layout.addWidget(self.preview)
        live_layout.addLayout(right_layout)

        self.log = QtWidgets.QTextEdit()
        self.log.setReadOnly(True)

        layout.addLayout(device_layout)
        layout.addLayout(audio_layout)
        layout.addLayout(folder_layout)
        layout.addWidget(QtWidgets.QLabel("Вопросы (режим список заранее)") )
        layout.addLayout(questions_layout)
        layout.addLayout(live_layout)
        layout.addWidget(QtWidgets.QLabel("Мини-лог событий"))
        layout.addWidget(self.log)

        self.setLayout(layout)

    def _setup_connections(self):
        self.thermal_check.clicked.connect(self._check_thermal)
        self.audio_check.clicked.connect(self._check_audio)
        self.folder_btn.clicked.connect(self._choose_folder)
        self.rec_btn.clicked.connect(self._toggle_recording)
        self.next_question_btn.clicked.connect(lambda: self._log_event("Вопрос зафиксирован"))
        self.answer_end_btn.clicked.connect(lambda: self._log_event("Ответ завершен"))
        self.event_btn.clicked.connect(lambda: self._log_event("Метка события"))
        self.audio_recorder.level_callback = self._on_audio_level
        self.instruction_btn.clicked.connect(self._show_instruction)

    def _check_thermal(self):
        self._start_adapter()
        self._log_event("Тепловизор проверен")

    def _check_audio(self):
        device = self.audio_combo.currentData()
        tmp = Path("sample/check.wav")
        tmp.parent.mkdir(exist_ok=True)
        rec = AudioRecorder(samplerate=self.config.audio_rate)
        rec.level_callback = self._on_audio_level
        rec.start(str(tmp), device_index=device)
        QtCore.QTimer.singleShot(5000, rec.stop)
        self._log_event("Проверка аудио 5 секунд")

    def _choose_folder(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Папка сессии")
        if path:
            self.folder_edit.setText(path)

    def _start_adapter(self):
        choice = self.thermal_combo.currentIndex()
        if choice == 0:
            self.adapter = DummyThermalAdapter()
            device = "0"
        else:
            self.adapter = FileThermalAdapter(self.file_adapter_path)
            device = str(self.file_adapter_path)
        self.adapter.open(device)

    def _toggle_recording(self):
        if self.frame_worker and self.frame_worker.isRunning():
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        if not self.folder_edit.text():
            QtWidgets.QMessageBox.warning(self, "Папка", "Выберите папку сохранения")
            return
        folder = Path(self.folder_edit.text())
        folder.mkdir(parents=True, exist_ok=True)
        self.session_folder = folder
        self._start_adapter()
        self.rec_indicator.show()
        self.truth_label.setText("Правда")
        self.rec_btn.setText("Закончить запись")
        self._log_event("Запись начата")
        self.start_time = time.monotonic()
        self._timer = QtCore.QTimer()
        self._timer.timeout.connect(self._update_timer)
        self._timer.start(500)
        self.deception_service = DeceptionService(self.config)
        self.frame_worker = FrameWorker(self.adapter, self.deception_service, self.config.frame_rate)
        self.frame_worker.frame_captured.connect(self._on_frame)
        self.frame_worker.error.connect(self._on_error)
        self.frame_worker.start()
        audio_device = self.audio_combo.currentData()
        self.audio_recorder.start(str(folder / "audio.wav"), device_index=audio_device)

    def _stop_recording(self):
        if self.frame_worker:
            self.frame_worker.stop()
            self.frame_worker.wait()
        if self.adapter:
            self.adapter.close()
        self.audio_recorder.stop()
        self.rec_indicator.hide()
        self.rec_btn.setText("Начать запись")
        self._timer.stop()
        self._log_event("Запись завершена")
        if self.session_folder and self.frame_worker:
            save_timeline(self.frame_worker.timeline, self.session_folder / "timeline.json")
        if self.video_writer is not None:
            self.video_writer.release()
            self.video_writer = None
        self.recording_stopped.emit(self.session_folder, self.frame_worker.timeline if self.frame_worker else [])

    def _update_timer(self):
        elapsed = int(time.monotonic() - self.start_time)
        self.timer_label.setText(f"{elapsed//60:02d}:{elapsed%60:02d}")

    def _on_frame(self, frame: np.ndarray, ts_ms: int, label: str, score: float):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        qimg = QtGui.QImage(rgb.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
        pix = QtGui.QPixmap.fromImage(qimg).scaled(self.preview.size(), QtCore.Qt.KeepAspectRatio)
        self.preview.setPixmap(pix)
        if self.session_folder:
            if self.video_writer is None:
                fourcc = cv2.VideoWriter_fourcc(*'H264')
                writer = cv2.VideoWriter(str(self.session_folder / "thermal_view.mp4"), fourcc, self.config.frame_rate, (w, h))
                if not writer.isOpened():
                    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                    writer = cv2.VideoWriter(str(self.session_folder / "thermal_view.mp4"), fourcc, self.config.frame_rate, (w, h))
                self.video_writer = writer
            if self.video_writer:
                bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
                self.video_writer.write(bgr)
        self.truth_label.setText(label)

    def _on_audio_level(self, level: float):
        level_db = min(int(level * 1000), 100)
        self.audio_level.setValue(level_db)

    def _on_error(self, message: str):
        QtWidgets.QMessageBox.critical(self, "Ошибка", message)
        self._stop_recording()

    def _log_event(self, text: str):
        self.log.append(f"[{time.strftime('%H:%M:%S')}] {text}")

    def _show_instruction(self):
        msg = (
            "1. Выберите тепловизор и микрофон, укажите папку сохранения.\n"
            "2. Добавьте вопросы или фиксируйте их по ходу.\n"
            "3. Нажмите 'Начать запись'. Индикатор покажет только 'Правда' или 'Ложь'.\n"
            "4. Во время записи используйте кнопки разметки для вопросов/ответов и событий.\n"
            "5. Нажмите 'Закончить запись', далее откроется окно разбора и экспорт в Excel."
        )
        QtWidgets.QMessageBox.information(self, "Инструкция", msg)
