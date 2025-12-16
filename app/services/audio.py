from __future__ import annotations
import queue
import threading
import sounddevice as sd
import soundfile as sf
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class AudioDevice:
    name: str
    index: int


class AudioRecorder:
    def __init__(self, samplerate: int = 16000, channels: int = 1):
        self.samplerate = samplerate
        self.channels = channels
        self._q: queue.Queue = queue.Queue()
        self._stream: Optional[sd.InputStream] = None
        self._file: Optional[sf.SoundFile] = None
        self._running = False
        self.level_callback: Optional[Callable[[float], None]] = None

    def list_devices(self) -> list[AudioDevice]:
        devices = []
        for idx, info in enumerate(sd.query_devices()):
            if info['max_input_channels'] > 0:
                devices.append(AudioDevice(info['name'], idx))
        return devices

    def start(self, filename: str, device_index: int | None = None):
        self._file = sf.SoundFile(filename, mode='w', samplerate=self.samplerate, channels=self.channels, subtype='PCM_16')
        self._running = True

        def callback(indata, frames, time, status):
            if status:
                print(status)
            self._q.put(indata.copy())
            if self.level_callback:
                level = float((indata**2).mean() ** 0.5)
                self.level_callback(level)

        self._stream = sd.InputStream(samplerate=self.samplerate, channels=self.channels, device=device_index, callback=callback)
        self._stream.start()
        threading.Thread(target=self._writer, daemon=True).start()

    def _writer(self):
        assert self._file is not None
        while self._running:
            try:
                data = self._q.get(timeout=0.5)
            except queue.Empty:
                continue
            self._file.write(data)
        self._file.close()

    def stop(self):
        self._running = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None


class VoiceprintService:
    def __init__(self, samplerate: int = 16000):
        self.samplerate = samplerate

    def list_devices(self):
        devices = []
        for idx, info in enumerate(sd.query_devices()):
            if info['max_input_channels'] > 0:
                devices.append(AudioDevice(info['name'], idx))
        return devices

    def record_voiceprint(self, seconds: int, device_index: int | None = None) -> bytes:
        data = sd.rec(int(seconds * self.samplerate), samplerate=self.samplerate, channels=1, device=device_index)
        sd.wait()
        # Fake embedding: compute simple statistics
        import numpy as np
        mean = float(np.mean(data))
        std = float(np.std(data))
        return f"{mean:.6f}:{std:.6f}".encode()

    def compare(self, voiceprint: bytes, sample: bytes) -> float:
        # Placeholder similarity
        return 1.0 if voiceprint == sample else 0.5
