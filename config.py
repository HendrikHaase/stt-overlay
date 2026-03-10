# User-editable configuration for SttOverlay

# Hotkey: hold this combination to record
# Supported modifier: "ctrl" (left or right Ctrl)
# Supported keys: see HOTKEY_VK_MAP below
HOTKEY_MOD = "ctrl"   # "ctrl" or "" for no modifier
HOTKEY_KEY = "Space"  # key name from HOTKEY_VK_MAP

# Windows Virtual Key code lookup table
HOTKEY_VK_MAP = {
    "Space":  0x20,
    "F1":     0x70,
    "F2":     0x71,
    "F3":     0x72,
    "F4":     0x73,
    "F5":     0x74,
    "F6":     0x75,
    "F7":     0x76,
    "F8":     0x77,
    "F9":     0x78,
    "F10":    0x79,
    "F11":    0x7A,
    "F12":    0x7B,
    "CapsLock": 0x14,
    "Tab":    0x09,
    "Enter":  0x0D,
    "Backspace": 0x08,
    "Delete": 0x2E,
    "Insert": 0x2D,
    "Home":   0x24,
    "End":    0x23,
    "PageUp": 0x21,
    "PageDown": 0x22,
    # Letters A-Z
    **{chr(c): c for c in range(ord('A'), ord('Z') + 1)},
    # Numbers 0-9
    **{str(n): 0x30 + n for n in range(10)},
}

# Resolve the VK code at import time
HOTKEY_VK = HOTKEY_VK_MAP.get(HOTKEY_KEY, 0x20)

# Audio
MODEL_NAME  = "nemo-parakeet-tdt-0.6b-v3"
SAMPLE_RATE = 16000   # Hz — Parakeet-v3 expects 16kHz
CHANNELS    = 1

# Overlay position
# MONITOR: "primary", or integer index (0, 1, 2, ...) for a specific monitor
MONITOR = "primary"

# ANCHOR: where on the monitor to place the overlay
# Valid values: "top_left"    "top_center"    "top_right"
#               "middle_left" "center"        "middle_right"
#               "bottom_left" "bottom_center" "bottom_right"
ANCHOR = "middle_right"

# Pixels between the overlay edge and the monitor edge
MARGIN = 20

# Overlay appearance
MAX_LINES = 20   # maximum number of transcription lines shown before oldest are dropped
