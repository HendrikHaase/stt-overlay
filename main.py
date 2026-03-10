"""
SttOverlay — entry point.

Thread architecture:
  Main thread  : Qt event loop + overlay window
  Hotkey       : QAbstractNativeEventFilter on the app (Raw Input, no hooks)
  Audio thread : sounddevice recording
  Infer thread : onnx-asr transcription
"""

import faulthandler
import os
import sys
import threading
import traceback

# faulthandler.enable()  # disabled: onnxruntime DLL init shows false-positive crashes

# Import onnxruntime BEFORE PyQt6 — Qt loads MSVC DLLs that conflict with
# onnxruntime's own copies if Qt wins the race. Pre-importing fixes the order.
try:
    import onnxruntime as _ort  # noqa: F401
except Exception:
    pass  # will be caught properly in Transcriber.__init__

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QApplication

from hotkey import HotkeyDetector
from overlay import OverlayWindow
from recorder import Recorder
from transcriber import Transcriber


class Controller(QObject):
    transcription_ready = pyqtSignal(str)

    def __init__(self, window: OverlayWindow, hotkey: HotkeyDetector):
        super().__init__()
        self._window   = window
        self._recorder = Recorder()
        self._transcriber: Transcriber | None = None
        self._model_error: str | None = None

        hotkey.key_pressed.connect(self._on_key_pressed)
        hotkey.key_released.connect(self._on_key_released)
        self.transcription_ready.connect(self._on_transcription_ready)

        threading.Thread(target=self._load_model, daemon=True).start()

    def _load_model(self):
        print("[SttOverlay] Loading Parakeet model... (first run downloads ~1.2 GB)")
        try:
            self._transcriber = Transcriber()
            print("[SttOverlay] Model ready.")
        except Exception as exc:
            print(f"[SttOverlay] Model load FAILED: {exc}")
            self._model_error = str(exc)

    @pyqtSlot()
    def _on_key_pressed(self):
        print("[SttOverlay] Recording started.")
        self._window.show_recording()
        threading.Thread(target=self._recorder.start, daemon=True).start()

    @pyqtSlot()
    def _on_key_released(self):
        print("[SttOverlay] Recording stopped, transcribing...")
        self._window.show_transcribing()
        threading.Thread(target=self._stop_and_transcribe, daemon=True).start()

    def _stop_and_transcribe(self):
        wav_path = self._recorder.stop()
        if self._model_error is not None:
            self.transcription_ready.emit("[model error - check console]")
            return
        if self._transcriber is None:
            self.transcription_ready.emit("[model loading, please retry]")
            return
        try:
            text = self._transcriber.transcribe(wav_path)
            print(f"[SttOverlay] Transcription: {text!r}")
        except Exception as exc:
            text = f"[error: {exc}]"
            print(f"[SttOverlay] Transcription error: {exc}")
        finally:
            try:
                os.remove(wav_path)
            except OSError:
                pass
        self.transcription_ready.emit(text)

    @pyqtSlot(str)
    def _on_transcription_ready(self, text: str):
        self._window.append_text(text)


def main():
    print("[SttOverlay] Starting...")

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    print("[SttOverlay] QApplication created.")

    try:
        window = OverlayWindow()
        print("[SttOverlay] Overlay window created.")
    except Exception:
        print("[SttOverlay] FATAL: failed to create overlay window:")
        traceback.print_exc()
        sys.exit(1)

    # Show the window so Qt allocates a native HWND, then apply Win32 flags.
    window.show()
    app.processEvents()
    window._apply_no_activate()
    print(f"[SttOverlay] Window shown. HWND={int(window.winId()):#x}")

    # Register Raw Input on the overlay's HWND via the app-level event filter.
    hotkey = HotkeyDetector()
    try:
        hotkey.install(app, int(window.winId()))
        print("[SttOverlay] Raw Input registered.")
    except Exception:
        print("[SttOverlay] WARNING: Raw Input registration failed:")
        traceback.print_exc()

    controller = Controller(window, hotkey)  # noqa: F841

    print(f"[SttOverlay] Ready. Hold Ctrl+{__import__('config').HOTKEY_KEY} to record.")
    ret = app.exec()
    print(f"[SttOverlay] Event loop exited ({ret}).")
    sys.exit(ret)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        input("Press Enter to close...")
        sys.exit(1)
