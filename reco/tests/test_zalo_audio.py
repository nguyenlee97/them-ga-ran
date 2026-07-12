import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch


sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.agent import transcription, zalo
from app import main


class _DownloadResponse:
    def __init__(self, chunks=None, url="https://voice-aac-dl.zdn.vn/v.aac", length=None):
        self._chunks = chunks or [b"aac"]
        self.url = url
        self.headers = {} if length is None else {"content-length": str(length)}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def raise_for_status(self):
        return None

    def iter_bytes(self):
        yield from self._chunks


class ZaloAudioTests(unittest.TestCase):
    def test_extracts_audio_url_from_signed_event_shape(self):
        body = {
            "event_name": "user_send_audio",
            "message": {"attachments": [{
                "type": "audio",
                "payload": {"url": "https://voice-aac-dl.zdn.vn/a/b.aac"},
            }]},
        }
        self.assertEqual(
            zalo.extract_audio_url(body),
            "https://voice-aac-dl.zdn.vn/a/b.aac",
        )

    def test_rejects_untrusted_or_non_https_audio_urls(self):
        for url in ("http://voice-aac-dl.zdn.vn/a.aac", "https://example.com/a.aac"):
            body = {
                "event_name": "user_send_audio",
                "message": {"attachments": [{"type": "audio", "payload": {"url": url}}]},
            }
            self.assertIsNone(zalo.extract_audio_url(body))

    def test_download_enforces_streaming_size_limit(self):
        with patch.object(zalo.config, "AUDIO_MAX_BYTES", 5), \
                patch.object(zalo._http, "stream", return_value=_DownloadResponse([b"123", b"456"])):
            with self.assertRaisesRegex(ValueError, "audio_too_large"):
                zalo.download_audio("https://voice-aac-dl.zdn.vn/a.aac")

    def test_transcription_converts_aac_and_posts_supported_wav(self):
        converted = SimpleNamespace(returncode=0, stdout=b"RIFF-wav", stderr=b"")
        api_response = SimpleNamespace(
            status_code=200,
            json=lambda: {"text": "Cho mình một combo gà."},
            text="",
        )
        with patch.object(transcription.config, "OPENAI_TRANSCRIBE_API_KEY", "test-key"), \
                patch.object(transcription.subprocess, "run", return_value=converted) as ffmpeg, \
                patch.object(transcription._client, "post", return_value=api_response) as post:
            text = transcription.transcribe_audio(b"raw-aac")
        self.assertEqual(text, "Cho mình một combo gà.")
        self.assertIn("ffmpeg", ffmpeg.call_args.args[0][0])
        self.assertEqual(post.call_args.kwargs["files"]["file"][0], "zalo-voice.wav")
        self.assertEqual(post.call_args.kwargs["data"]["language"], "vi")

    def test_audio_handler_reuses_the_existing_text_flow(self):
        with patch.object(zalo, "download_audio", return_value=b"aac"), \
                patch.object(transcription, "transcribe_audio", return_value="xem menu"), \
                patch.object(main, "_handle_zalo_message") as handle_text:
            main._handle_zalo_audio("zalo-1", "https://voice-aac-dl.zdn.vn/a.aac")
        handle_text.assert_called_once_with("zalo-1", "xem menu")


if __name__ == "__main__":
    unittest.main()
