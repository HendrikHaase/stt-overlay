"""Parakeet-v3 transcription wrapper using onnx-asr."""

import config


class Transcriber:
    def __init__(self):
        # Defer import so a missing/broken onnxruntime DLL doesn't crash the app
        # on import — the error surfaces here with a clear message instead.
        try:
            import onnx_asr
        except ImportError as exc:
            raise RuntimeError(
                f"Failed to import onnx_asr / onnxruntime: {exc}\n"
                "Fix: pip uninstall onnxruntime onnxruntime-gpu -y && pip install onnxruntime\n"
                "If that fails, install VC++ Redistributable 2022 x64 from Microsoft."
            ) from exc

        # Downloads the model on first call (~1.2 GB cached in ~/.cache/onnx_asr/)
        self.model = onnx_asr.load_model(config.MODEL_NAME)

    def transcribe(self, wav_path: str) -> str:
        """Transcribe a WAV file and return the stripped text."""
        result = self.model.recognize(wav_path)
        if isinstance(result, str):
            return result.strip()
        return str(result).strip()
