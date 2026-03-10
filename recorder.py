"""Audio recording via sounddevice (WASAPI on Windows)."""

import tempfile

import numpy as np
import sounddevice as sd
import soundfile as sf

import config


class Recorder:
    def __init__(self):
        self._frames: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None

    def start(self) -> None:
        """Begin capturing microphone audio."""
        self._frames = []
        self._stream = sd.InputStream(
            samplerate=config.SAMPLE_RATE,
            channels=config.CHANNELS,
            dtype="float32",
            callback=self._callback,
        )
        self._stream.start()

    def _callback(self, indata: np.ndarray, frames: int, time, status) -> None:
        self._frames.append(indata.copy())

    def stop(self) -> str:
        """Stop capturing and save to a temp WAV file. Returns the file path."""
        if self._stream is None:
            raise RuntimeError("stop() called without a matching start()")
        self._stream.stop()
        self._stream.close()
        self._stream = None

        if not self._frames:
            # Return silence if nothing was captured
            audio = np.zeros((config.SAMPLE_RATE // 10, config.CHANNELS), dtype="float32")
        else:
            audio = np.concatenate(self._frames, axis=0)

        path = tempfile.mktemp(suffix=".wav")
        sf.write(path, audio, config.SAMPLE_RATE)
        return path
