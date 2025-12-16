from __future__ import annotations
from PySide6 import QtWidgets
from PySide6.QtWidgets import QListWidgetItem, QMessageBox
from app.storage import Storage
from app.services.audio import VoiceprintService


class CreateUserDialog(QtWidgets.QDialog):
    def __init__(self, storage: Storage, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.setWindowTitle("Создать пользователя")
        self.name_edit = QtWidgets.QLineEdit()
        self.record_checkbox = QtWidgets.QCheckBox("Запомнить голос пользователя")
        self.seconds_spin = QtWidgets.QSpinBox()
        self.seconds_spin.setRange(30, 60)
        self.seconds_spin.setValue(30)
        self.device_combo = QtWidgets.QComboBox()
        self.voice_service = VoiceprintService()
        self._load_devices()
        form = QtWidgets.QFormLayout()
        form.addRow("ФИО*", self.name_edit)
        form.addRow("Длительность (сек)", self.seconds_spin)
        form.addRow("Микрофон", self.device_combo)
        form.addRow(self.record_checkbox)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(btns)
        self.setLayout(layout)
        self.voiceprint: bytes | None = None

    def _load_devices(self):
        self.device_combo.addItem("По умолчанию", None)
        try:
            for dev in self.voice_service.list_devices():
                self.device_combo.addItem(dev.name, dev.index)
        except Exception:
            # sounddevice not initialised yet; silent
            pass

    def accept(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Ошибка", "Введите ФИО")
            return
        if self.record_checkbox.isChecked():
            try:
                device = self.device_combo.currentData()
                self.voiceprint = self.voice_service.record_voiceprint(self.seconds_spin.value(), device_index=device)
            except Exception as exc:
                QMessageBox.warning(self, "Запись", f"Не удалось записать голос: {exc}")
                self.voiceprint = None
        user = self.storage.create_user(name, self.voiceprint)
        self.created_user = user
        super().accept()


class UserSelection(QtWidgets.QWidget):
    def __init__(self, storage: Storage):
        super().__init__()
        self.storage = storage
        self.list = QtWidgets.QListWidget()
        self.create_btn = QtWidgets.QPushButton("Создать пользователя")
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(QtWidgets.QLabel("Выберите пользователя"))
        layout.addWidget(self.list)
        layout.addWidget(self.create_btn)
        self.setLayout(layout)
        self.selected_user = None
        self.create_btn.clicked.connect(self._on_create)
        self.list.itemDoubleClicked.connect(self._on_select)
        self.refresh()

    def refresh(self):
        self.list.clear()
        for user in self.storage.list_users():
            item = QListWidgetItem(user.full_name)
            item.setData(QtCore.Qt.UserRole, user)
            self.list.addItem(item)

    def _on_create(self):
        dialog = CreateUserDialog(self.storage, self)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            self.refresh()

    def _on_select(self, item: QListWidgetItem):
        self.selected_user = item.data(QtCore.Qt.UserRole)
        self.parent().close()


from PySide6 import QtCore  # placed last to avoid PySide cyclic import warnings
