"""Channel-agnostic completed-audio transcription for the ordering agent."""
import subprocess

import httpx

from app.config import config


class TranscriptionError(RuntimeError):
    pass


_client = httpx.Client(timeout=60.0)


def _aac_to_wav(audio: bytes) -> bytes:
    """Convert Zalo's raw AAC to an OpenAI-supported 16 kHz mono WAV."""
    if not audio:
        raise TranscriptionError("empty_audio")
    command = [
        "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
        "-i", "pipe:0",
        "-t", str(config.AUDIO_MAX_SECONDS),
        "-ac", "1", "-ar", "16000",
        "-f", "wav", "pipe:1",
    ]
    try:
        result = subprocess.run(
            command,
            input=audio,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=45,
            check=False,
        )
    except FileNotFoundError as exc:
        raise TranscriptionError("ffmpeg_not_installed") from exc
    except subprocess.TimeoutExpired as exc:
        raise TranscriptionError("audio_conversion_timeout") from exc
    if result.returncode != 0 or not result.stdout:
        detail = result.stderr.decode("utf-8", errors="replace")[:200]
        raise TranscriptionError(f"audio_conversion_failed:{detail}")
    if len(result.stdout) > config.AUDIO_MAX_BYTES:
        raise TranscriptionError("converted_audio_too_large")
    return result.stdout


def transcribe_audio(audio: bytes) -> str:
    """Convert a completed Zalo AAC note and transcribe it as Vietnamese text."""
    if not config.OPENAI_TRANSCRIBE_API_KEY:
        raise TranscriptionError("missing_openai_transcribe_api_key")
    wav = _aac_to_wav(audio)
    try:
        response = _client.post(
            f"{config.OPENAI_TRANSCRIBE_BASE_URL}/audio/transcriptions",
            headers={"Authorization": f"Bearer {config.OPENAI_TRANSCRIBE_API_KEY}"},
            data={
                "model": config.OPENAI_TRANSCRIBE_MODEL,
                "language": "vi",
                "response_format": "json",
                "prompt": (
                    "Khách đang đặt món KFC Việt Nam. Từ vựng có thể gồm KFC, gà rán, "
                    "combo, burger, cơm, mì Ý, Pepsi, voucher, COD, QR và địa chỉ Việt Nam."
                ),
            },
            files={"file": ("zalo-voice.wav", wav, "audio/wav")},
        )
    except Exception as exc:
        raise TranscriptionError(f"transcription_request_failed:{type(exc).__name__}") from exc
    if response.status_code >= 400:
        raise TranscriptionError(
            f"transcription_http_{response.status_code}:{response.text[:200]}"
        )
    try:
        text = (response.json().get("text") or "").strip()
    except Exception as exc:
        raise TranscriptionError("invalid_transcription_response") from exc
    if not text:
        raise TranscriptionError("empty_transcription")
    return text
