from __future__ import annotations
import cv2
import numpy as np
from pathlib import Path
from typing import List, Optional


class ThermalFrame:
    def __init__(self, frame: np.ndarray, temperature_matrix: Optional[np.ndarray] = None):
        self.frame = frame
        self.temperature_matrix = temperature_matrix


class ThermalAdapter:
    """Base class for thermal camera adapters."""

    def list_devices(self) -> List[str]:
        raise NotImplementedError

    def open(self, device: str):
        raise NotImplementedError

    def read_frame(self) -> ThermalFrame:
        raise NotImplementedError

    def close(self):
        raise NotImplementedError


class DummyThermalAdapter(ThermalAdapter):
    """Uses a standard webcam to simulate thermal output."""

    def __init__(self):
        self.cap: Optional[cv2.VideoCapture] = None

    def list_devices(self) -> List[str]:
        # In practice we guess first few indices
        return ["0", "1", "2"]

    def open(self, device: str):
        idx = int(device)
        self.cap = cv2.VideoCapture(idx)
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open camera {device}")

    def read_frame(self) -> ThermalFrame:
        if not self.cap:
            raise RuntimeError("Camera not opened")
        ret, frame = self.cap.read()
        if not ret:
            raise RuntimeError("Failed to read frame")
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # Fake thermal coloring
        normalized = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
        thermal = cv2.applyColorMap(normalized, cv2.COLORMAP_JET)
        return ThermalFrame(thermal)

    def close(self):
        if self.cap:
            self.cap.release()
            self.cap = None


class FileThermalAdapter(ThermalAdapter):
    def __init__(self, video_path: Path):
        self.video_path = video_path
        self.cap: Optional[cv2.VideoCapture] = None

    def list_devices(self) -> List[str]:
        if self.video_path.exists():
            return [str(self.video_path)]
        return []

    def open(self, device: str):
        path = Path(device)
        self.cap = cv2.VideoCapture(str(path))
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open file {device}")

    def read_frame(self) -> ThermalFrame:
        if not self.cap:
            raise RuntimeError("File not opened")
        ret, frame = self.cap.read()
        if not ret:
            # loop
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.cap.read()
            if not ret:
                raise RuntimeError("Failed to read frame")
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        thermal = cv2.applyColorMap(gray, cv2.COLORMAP_PLASMA)
        return ThermalFrame(thermal)

    def close(self):
        if self.cap:
            self.cap.release()
            self.cap = None


class VendorThermalAdapter(ThermalAdapter):
    """Skeleton for vendor SDK integration.

    TODO: integrate vendor-specific SDK: initialize SDK, enumerate devices, open streams,
    and convert frames to numpy arrays. Refer to vendor documentation and replace
    NotImplementedError sections.
    """

    def __init__(self):
        self._connected = False

    def list_devices(self) -> List[str]:
        # TODO: query SDK for available devices
        return []

    def open(self, device: str):
        # TODO: open device using SDK
        self._connected = True
        raise NotImplementedError("Vendor SDK integration required")

    def read_frame(self) -> ThermalFrame:
        if not self._connected:
            raise RuntimeError("Device not open")
        raise NotImplementedError("Vendor SDK integration required")

    def close(self):
        # TODO: close SDK handles
        self._connected = False
