"""Речевой канал демонстрационного стенда: распознавание и синтез — локально.

Распознавание — faster-whisper (тот же Whisper, что в ADR-0009, но маленький
чекпоинт: на MacBook он считается на CPU за единицы секунд). Синтез — штатный
голос macOS Milena. Ни один фрагмент звука не уходит с машины.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

MODELS = {
    "tiny": "самый быстрый, путает термины",
    "base": "разумный компромисс для демонстрации",
    "small": "точнее на медицинских словах, заметно медленнее",
}


@lru_cache(maxsize=3)
def _asr(size: str):
    from faster_whisper import WhisperModel

    return WhisperModel(size, device="cpu", compute_type="int8")


def asr_available() -> bool:
    try:
        import faster_whisper  # noqa: F401
    except Exception:
        return False
    return True


def transcribe(audio: bytes, size: str = "base") -> tuple[str, float]:
    """Вернуть текст реплики и время распознавания в секундах."""
    import time

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
        handle.write(audio)
        path = Path(handle.name)
    started = time.perf_counter()
    try:
        segments, _ = _asr(size).transcribe(str(path), language="ru", vad_filter=True)
        text = " ".join(segment.text.strip() for segment in segments).strip()
    finally:
        path.unlink(missing_ok=True)
    return text, time.perf_counter() - started


def tts_available() -> bool:
    return shutil.which("say") is not None


def synthesize(text: str, voice: str = "Milena") -> bytes | None:
    """Озвучить ответ штатным голосом macOS. Возвращает WAV."""
    if not tts_available() or not text.strip():
        return None
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
        path = Path(handle.name)
    try:
        subprocess.run(
            ["say", "-v", voice, "--data-format=LEI16@22050", "-o", str(path), text],
            check=True,
            capture_output=True,
            timeout=60,
        )
        return path.read_bytes()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    finally:
        path.unlink(missing_ok=True)
