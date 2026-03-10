"""
Win32 Raw Input hotkey detector.

Uses RegisterRawInputDevices + RIDEV_INPUTSINK so WM_INPUT arrives even when
the app is unfocused — no SetWindowsHookEx, no global hook, no injection.

Architecture:
  _RawInputFilter  — QAbstractNativeEventFilter installed on QApplication
                     intercepts WM_INPUT at the app level (no nativeEvent
                     override on any widget, which crashes on Python 3.12)
  HotkeyDetector   — QObject that owns the filter and emits Qt signals
"""

import ctypes
import ctypes.wintypes

from PyQt6.QtCore import QAbstractNativeEventFilter, QObject, pyqtSignal

import config

# ── Win32 constants ──────────────────────────────────────────────────────────
RIDEV_INPUTSINK            = 0x00000100
HID_USAGE_PAGE_GENERIC     = 0x01
HID_USAGE_GENERIC_KEYBOARD = 0x06
WM_INPUT                   = 0x00FF
RID_INPUT                  = 0x10000003
RAWINPUT_HEADER_SIZE       = 24   # sizeof(RAWINPUTHEADER) on 64-bit Windows

# RAWKEYBOARD field offsets from start of RAWINPUT buffer
_RAWKB_OFFSET_FLAGS = RAWINPUT_HEADER_SIZE + 2   # 26
_RAWKB_OFFSET_VKEY  = RAWINPUT_HEADER_SIZE + 6   # 30

RI_KEY_BREAK = 0x0001
VK_CONTROL   = 0x11   # generic Ctrl (what Raw Input often reports)
VK_LCONTROL  = 0xA2
VK_RCONTROL  = 0xA3
VK_CTRL_SET  = {VK_CONTROL, VK_LCONTROL, VK_RCONTROL}


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", ctypes.c_ushort),
        ("usUsage",     ctypes.c_ushort),
        ("dwFlags",     ctypes.c_uint),
        ("hwndTarget",  ctypes.c_void_p),
    ]


def register_raw_input(hwnd: int) -> None:
    """Register the given HWND to receive raw keyboard input even when unfocused."""
    rid = RAWINPUTDEVICE(
        HID_USAGE_PAGE_GENERIC,
        HID_USAGE_GENERIC_KEYBOARD,
        RIDEV_INPUTSINK,
        hwnd,
    )
    ok = ctypes.windll.user32.RegisterRawInputDevices(
        ctypes.byref(rid), 1, ctypes.sizeof(rid)
    )
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())


# ── Native event filter (NOT a QWidget subclass — avoids vtable corruption) ──
class _RawInputFilter(QAbstractNativeEventFilter):
    """Installed on QApplication; routes WM_INPUT to the detector."""

    def __init__(self, detector: "HotkeyDetector"):
        super().__init__()
        self._detector = detector

    def nativeEventFilter(self, event_type, message):
        if event_type == b"windows_generic_MSG":
            try:
                msg = ctypes.wintypes.MSG.from_address(int(message))
                if msg.message == WM_INPUT:
                    self._detector._handle_raw_input(msg.lParam)
            except Exception as e:
                print(f"[Hotkey] nativeEventFilter error: {e}", flush=True)
        return False, 0


# ── Public API ────────────────────────────────────────────────────────────────
class HotkeyDetector(QObject):
    key_pressed  = pyqtSignal()
    key_released = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._ctrl_held = False
        self._recording = False
        self._filter = _RawInputFilter(self)   # keep reference alive

    def install(self, app, hwnd: int) -> None:
        """Register Raw Input on hwnd and install the native event filter."""
        register_raw_input(hwnd)
        app.installNativeEventFilter(self._filter)
        print(f"[Hotkey] Filter installed on app, Raw Input registered on HWND={hwnd:#x}", flush=True)

    # ── Raw input parsing ─────────────────────────────────────────────────────
    def _handle_raw_input(self, lParam):
        size = ctypes.c_uint(0)
        ctypes.windll.user32.GetRawInputData(
            lParam, RID_INPUT, None, ctypes.byref(size), RAWINPUT_HEADER_SIZE
        )
        if size.value == 0:
            return
        buf = (ctypes.c_byte * size.value)()
        read = ctypes.windll.user32.GetRawInputData(
            lParam, RID_INPUT, buf, ctypes.byref(size), RAWINPUT_HEADER_SIZE
        )
        if read == 0 or read > size.value:
            return
        if size.value < _RAWKB_OFFSET_VKEY + 2:
            return

        flags = ctypes.c_ushort.from_buffer(buf, _RAWKB_OFFSET_FLAGS).value
        vkey  = ctypes.c_ushort.from_buffer(buf, _RAWKB_OFFSET_VKEY).value
        is_up = bool(flags & RI_KEY_BREAK)

        self._update_key_state(vkey, is_up)

    def _update_key_state(self, vkey: int, is_up: bool):
        if vkey in VK_CTRL_SET:
            self._ctrl_held = not is_up

        if vkey == config.HOTKEY_VK:
            needs_mod = config.HOTKEY_MOD == "ctrl"
            if not is_up:
                mod_ok = (not needs_mod) or self._ctrl_held
                if mod_ok and not self._recording:
                    self._recording = True
                    self.key_pressed.emit()
            else:
                if self._recording:
                    self._recording = False
                    self.key_released.emit()
