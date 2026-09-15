"""Voice boundary (FR-23, OQ-04 provider TBD).

The transcript is always the source of truth — audio never bypasses the
text pipeline, guardrails, or citation contract.

- BrowserSpeechProvider: the local demo path — Web Speech API
  (SpeechRecognition / speechSynthesis) runs entirely client-side in the
  Angular app; the server only ever sees text. Zero credentials.
- PollySpeechProvider: server-side STT/TTS via AWS Transcribe + Polly for
  telephony/Genesys audio. Skeleton until AWS credentials exist.
"""

from typing import Protocol


class SpeechProvider(Protocol):
    def transcribe(self, audio: bytes, language: str = "en") -> str: ...
    def synthesize(self, text: str, language: str = "en") -> bytes: ...


class BrowserSpeechProvider:
    """Marker for client-side voice — the Angular app owns audio; the
    transcript flows through the same /messages:stream endpoint."""

    def transcribe(self, audio: bytes, language: str = "en") -> str:
        raise NotImplementedError("client-side STT — browser owns audio")

    def synthesize(self, text: str, language: str = "en") -> bytes:
        raise NotImplementedError("client-side TTS — browser owns audio")


class PollySpeechProvider:
    """AWS Transcribe (STT) + Polly (TTS) — enabled when boto3/credentials
    and REGINTEL_SPEECH_PROVIDER=aws are configured."""

    def __init__(self):
        try:
            import boto3

            self._polly = boto3.client("polly")
            self._transcribe = boto3.client("transcribe")
        except Exception:
            self._polly = self._transcribe = None

    @property
    def available(self) -> bool:
        return self._polly is not None

    def synthesize(self, text: str, language: str = "en") -> bytes:
        if not self._polly:
            raise RuntimeError("Polly not configured")
        resp = self._polly.synthesize_speech(Text=text, OutputFormat="mp3", VoiceId="Joanna")
        return resp["AudioStream"].read()

    def transcribe(self, audio: bytes, language: str = "en") -> str:
        # Real path: Transcribe streaming job → transcript. Skeleton until
        # credentials exist.
        raise RuntimeError("Transcribe not configured")


def get_speech_provider(configured: str = "browser") -> SpeechProvider:
    if configured == "aws":
        return PollySpeechProvider()
    return BrowserSpeechProvider()
