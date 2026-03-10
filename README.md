# SttOverlay — Project Overview

Push-to-talk speech-to-text overlay for gaming. Hold Ctrl+Space, speak, release — transcription appears in a dark frameless overlay that stays on top of any game without stealing focus.

## Stack

| Role | Library |
|---|---|
| Global hotkey | Win32 Raw Input via `ctypes` (`RegisterRawInputDevices` + `QAbstractNativeEventFilter`) |
| Audio recording | `sounddevice` + `soundfile` |
| Transcription | `onnx-asr` (Parakeet-v3 model) |
| Overlay GUI | `PyQt6` |

## File Map

```
config.py       — all user-editable settings (hotkey, model, monitor, anchor, colors)
main.py         — entry point; wires Controller + HotkeyDetector + OverlayWindow
overlay.py      — PyQt6 frameless dark overlay window (plain QWidget, no nativeEvent override)
hotkey.py       — HotkeyDetector (QObject) + _RawInputFilter (QAbstractNativeEventFilter)
recorder.py     — sounddevice mic capture → temp WAV file
transcriber.py  — onnx-asr wrapper (load_model / recognize)
requirements.txt
build.bat       — PyInstaller --onedir build
```

## How It Works

1. `main.py` creates `QApplication`, shows `OverlayWindow`, registers Raw Input on its HWND
2. `HotkeyDetector` installs `_RawInputFilter` on the app — intercepts `WM_INPUT` messages
3. On Ctrl+Space down → `key_pressed` signal → `Recorder.start()` in a thread
4. On Ctrl+Space up → `key_released` signal → `Recorder.stop()` saves WAV → `Transcriber.recognize()` in a thread
5. `transcription_ready` signal (thread-safe) → `OverlayWindow.append_text()` on main thread

## Key Architecture Decisions & Hard-Won Fixes

### Do NOT override `nativeEvent` on QWidget
Overriding `nativeEvent` in a PyQt6 QWidget subclass with multiple inheritance crashes on Python 3.12 (vtable corruption). Use `QAbstractNativeEventFilter` installed on the app instead. This is in `hotkey.py` as `_RawInputFilter`.

### Import onnxruntime before PyQt6
PyQt6 loads MSVC DLLs that conflict with onnxruntime if Qt loads first. `main.py` does `import onnxruntime` at the top before any PyQt6 imports to win the DLL load order race.

### winId() requires show() first
PyQt6 on Windows doesn't allocate a native HWND until the window is shown. `main.py` calls `window.show()` + `app.processEvents()` before calling `window.winId()` or registering Raw Input.

### VK_CONTROL is 0x11, not just 0xA2/0xA3
Raw Input often reports the generic `VK_CONTROL` (0x11) rather than `VK_LCONTROL`/`VK_RCONTROL`. `VK_CTRL_SET = {0x11, 0xA2, 0xA3}`.

### onnx-asr API
```python
model = onnx_asr.load_model("nemo-parakeet-tdt-0.6b-v3")
result = model.recognize("path/to/file.wav")   # returns str
```
Not `load()` / `transcribe()` — those don't exist.

### setQuitOnLastWindowClosed(False)
The overlay can be hidden (Close button) without quitting the app. Next transcription re-shows it.

## Config Reference (`config.py`)

```python
HOTKEY_MOD = "ctrl"          # "ctrl" or "" for no modifier
HOTKEY_KEY = "Space"         # key name from HOTKEY_VK_MAP
MODEL_NAME = "nemo-parakeet-tdt-0.6b-v3"
SAMPLE_RATE = 16000
MONITOR = "primary"          # or integer index (0, 1, 2...)
ANCHOR = "middle_right"      # top/middle/bottom + left/center/right
MARGIN = 20                  # px from screen edge
MAX_LINES = 20               # oldest lines dropped when exceeded
```

## Running

```bat
pip install -r requirements.txt
python main.py
```

First run downloads the Parakeet model (~1.2 GB, cached in `~/.cache/onnx_asr/`).

## Building

```bat
build.bat
# output: dist\SttOverlay\SttOverlay.exe
```
