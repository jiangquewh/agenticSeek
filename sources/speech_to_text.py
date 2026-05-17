#!/usr/bin/env python3
"""
Speech-to-Text wrapper class for Vosk API.

Provides a high-level interface for real-time microphone-based speech recognition,
suitable for AI applications requiring voice input.

Prerequisites:
    - Vosk: pip install vosk
    - SoundDevice: pip install sounddevice
    - NumPy: pip install numpy
    - Download a model from https://alphacephei.com/vosk/models
"""

import json
import queue
import sys
import threading
from typing import Callable, List, Optional, Dict, Any

from colorama import Fore

from sources.echo_filter import filter_echo

IMPORT_FOUND = True
try:
    import sounddevice as sd
    from vosk import Model, KaldiRecognizer, SetLogLevel
except ImportError:
    print(Fore.RED + "Speech To Text disabled. Install with: pip install vosk sounddevice" + Fore.RESET)
    IMPORT_FOUND = False

# Global callback registry for TTS state notifications
_tts_start_callbacks: List[Callable[[], None]] = []
_tts_stop_callbacks: List[Callable[[], None]] = []


def register_tts_start_callback(callback: Callable[[], None]) -> None:
    """Register a callback fired when TTS starts speaking."""
    _tts_start_callbacks.append(callback)


def register_tts_stop_callback(callback: Callable[[], None]) -> None:
    """Register a callback fired when TTS stops speaking."""
    _tts_stop_callbacks.append(callback)


def notify_tts_start() -> None:
    """Notify all registered callbacks that TTS has started."""
    for callback in _tts_start_callbacks:
        try:
            callback()
        except Exception:
            pass


def notify_tts_stop() -> None:
    """Notify all registered callbacks that TTS has stopped."""
    for callback in _tts_stop_callbacks:
        try:
            callback()
        except Exception:
            pass


class Speech2Text:
    """
    A wrapper class for Vosk speech-to-text with microphone input.

    Provides real-time speech recognition with support for partial results,
    grammar constraints, word-level timing, and echo filtering of TTS output.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        lang: str = "en-us",
        sample_rate: Optional[int] = None,
        device: Optional[int] = None,
        block_size: int = 8000,
        grammar: Optional[List[str]] = None,
        max_alternatives: int = 1,
        enable_words: bool = False,
        enable_partial_words: bool = False,
        log_level: int = -1,
    ):
        """
        Initialize the Speech2Text recognizer.

        Args:
            model_path: Path to local Vosk model folder. If None, downloads model for `lang`.
            lang: Language code (e.g., "en-us", "fr"). Ignored if model_path is set.
            sample_rate: Audio sample rate. Auto-detected from device if None.
            device: Audio input device ID. Uses default if None.
            block_size: Audio buffer size in samples.
            grammar: Optional list of phrases for constrained recognition.
            max_alternatives: Maximum number of alternative transcriptions to return.
            enable_words: Enable word-level timestamps in results.
            enable_partial_words: Enable word-level timestamps for partial results.
            log_level: Vosk log level (0=normal, -1=silent).
        """
        if not IMPORT_FOUND:
            return

        SetLogLevel(log_level)

        self.device = device
        self.block_size = block_size
        self._running = False
        self._audio_queue: queue.Queue = queue.Queue()

        if sample_rate is None:
            device_info = sd.query_devices(device, "input")
            self.sample_rate = int(device_info["default_samplerate"])
        else:
            self.sample_rate = sample_rate

        self.model = Model(model_path) if model_path else Model(lang=lang)

        if grammar:
            grammar_str = json.dumps(grammar + ["[unk]"])
            self.recognizer = KaldiRecognizer(self.model, self.sample_rate, grammar_str)
        else:
            self.recognizer = KaldiRecognizer(self.model, self.sample_rate)

        if max_alternatives > 1:
            self.recognizer.SetMaxAlternatives(max_alternatives)
        if enable_words:
            self.recognizer.SetWords(True)
        if enable_partial_words:
            self.recognizer.SetPartialWords(True)

        self._stream: Optional[sd.RawInputStream] = None
        self._muted = False
        self._muted_lock = threading.Lock()

        register_tts_start_callback(self._on_tts_start)
        register_tts_stop_callback(self._on_tts_stop)

    def _audio_callback(self, indata, frames, time, status):
        """Internal callback for the sounddevice audio stream."""
        if status:
            print(f"Audio status: {status}", file=sys.stderr)
        self._audio_queue.put(bytes(indata))

    def start_listening(self) -> None:
        """Start capturing audio from the microphone."""
        if not IMPORT_FOUND or self._running:
            return
        self._running = True
        self._stream = sd.RawInputStream(
            samplerate=self.sample_rate,
            blocksize=self.block_size,
            device=self.device,
            dtype="int16",
            channels=1,
            callback=self._audio_callback,
        )
        self._stream.start()

    def stop_listening(self) -> None:
        """Stop capturing audio from the microphone."""
        self._running = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def is_listening(self) -> bool:
        """Return True if the audio stream is currently active."""
        return self._running

    def is_muted(self) -> bool:
        """Return True if audio is currently being discarded."""
        with self._muted_lock:
            return self._muted

    def mute(self) -> None:
        """Discard incoming audio without stopping the stream."""
        with self._muted_lock:
            self._muted = True
            while not self._audio_queue.empty():
                try:
                    self._audio_queue.get_nowait()
                except queue.Empty:
                    break
            self.recognizer.Reset()

    def unmute(self) -> None:
        """Resume processing of incoming audio."""
        with self._muted_lock:
            self._muted = False

    def _on_tts_start(self) -> None:
        """TTS start handler — mute mic to avoid self-echo."""
        self.mute()

    def _on_tts_stop(self) -> None:
        """TTS stop handler — resume listening."""
        self.unmute()

    def process_audio(self, audio_data: bytes) -> Optional[Dict[str, Any]]:
        """
        Process a chunk of audio data.

        Args:
            audio_data: Raw PCM audio bytes (16-bit, mono).

        Returns:
            Dict with recognition result if a complete utterance is detected,
            None otherwise.
        """
        if self.recognizer.AcceptWaveform(audio_data):
            return json.loads(self.recognizer.Result())
        return None

    def get_partial(self) -> Dict[str, Any]:
        """Return the current interim recognition result."""
        return json.loads(self.recognizer.PartialResult())

    def get_final(self) -> Dict[str, Any]:
        """Return the final recognition result, flushing the recognizer."""
        return json.loads(self.recognizer.FinalResult())

    def get_result(self, last_spoken: str = "", timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Pull the next available recognition result from the audio queue.

        Args:
            last_spoken: Most recent TTS output, used to filter self-echo.
            timeout: Max seconds to wait for audio data.

        Returns:
            Dict with recognition result if a complete (non-echo) utterance is
            detected, None on timeout, mute, or when the result is an echo.
        """
        if self.is_muted():
            try:
                while True:
                    self._audio_queue.get_nowait()
            except queue.Empty:
                pass
            return None

        try:
            data = self._audio_queue.get(timeout=timeout)
            if self.is_muted():
                return None
            result = self.process_audio(data)
            if result:
                text = result.get("text", "").strip()
                if text and filter_echo(text, last_spoken):
                    return result
        except queue.Empty:
            pass
        return None

    def reset(self) -> None:
        """Reset the recognizer state, clearing any partial result."""
        self.recognizer.Reset()

    def set_grammar(self, phrases: List[str]) -> None:
        """Dynamically update the recognition grammar."""
        grammar_str = json.dumps(phrases + ["[unk]"])
        self.recognizer.SetGrammar(grammar_str)

    @staticmethod
    def list_devices() -> List[Dict[str, Any]]:
        """Return a list of available audio input devices."""
        if not IMPORT_FOUND:
            return []
        devices = sd.query_devices()
        return [
            {
                "id": i,
                "name": device["name"],
                "channels": device["max_input_channels"],
                "sample_rate": device["default_samplerate"],
            }
            for i, device in enumerate(devices)
            if device["max_input_channels"] > 0
        ]

    def __enter__(self):
        self.start_listening()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_listening()


if __name__ == "__main__":
    print("Initializing Speech2Text...")
    s2t = Speech2Text(lang="en-us")
    print("Speak into your microphone. Ctrl+C to stop.")
    try:
        with s2t:
            while True:
                result = s2t.get_result(timeout=0.1)
                if result and result.get("text"):
                    print(f"[FINAL] {result['text']}")
    except KeyboardInterrupt:
        print("\nStopped.")
