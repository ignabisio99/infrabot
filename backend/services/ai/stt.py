"""Speech-to-text de notas de voz (WhatsApp o formulario web → texto).

El endpoint OpenAI-compatible de Gemini no soporta /audio/transcriptions, así que
para Gemini se usa la API nativa generateContent con el audio inline en base64.
Con AI_PROVIDER=mock devuelve un transcript fijo configurable (AI_STT_MOCK_TEXTO).
"""

from __future__ import annotations

import base64
import logging
import os
import subprocess
import tempfile
import time
import wave

import httpx
import numpy as np

from core.ai import config as ai_config

logger = logging.getLogger(__name__)

_PROMPT_TRANSCRIPCION = (
    "Transcribí literalmente este audio en español. "
    "Respondé solo con el texto transcripto, sin comillas ni comentarios."
)

_MIME_GEMINI = {
    "audio/ogg": "audio/ogg",
    "audio/opus": "audio/ogg",
    "audio/mpeg": "audio/mpeg",
    "audio/mp3": "audio/mpeg",
    "audio/mp4": "audio/mp4",
    "audio/m4a": "audio/mp4",
    "audio/x-m4a": "audio/mp4",
    "audio/wav": "audio/wav",
    "audio/x-wav": "audio/wav",
    "audio/webm": "audio/webm",
    "audio/aac": "audio/aac",
    "audio/amr": "audio/amr",
}

_EXT_WHISPER = {
    "audio/ogg": "ogg",
    "audio/opus": "ogg",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/mp4": "m4a",
    "audio/m4a": "m4a",
    "audio/x-m4a": "m4a",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/webm": "webm",
    "audio/aac": "aac",
    "audio/amr": "amr",
}


class TranscripcionError(Exception):
    """Falló la transcripción del audio."""


def _mime_base(mime_type: str) -> str:
    return (mime_type or "audio/ogg").split(";")[0].strip().lower() or "audio/ogg"


_whisper_local = None

_ARCHIVOS_WHISPER = ("config.json", "model.bin", "tokenizer.json", "vocabulary.txt")


def _cache_modelo_whisper(modelo: str) -> str:
    """Directorio del modelo. Si AI_SSL_VERIFY=false, lo baja con httpx (proxy corporativo)."""
    if os.path.isdir(modelo):
        return modelo
    cache = os.path.join(
        os.getenv("AI_STT_MODEL_DIR") or os.path.join(tempfile.gettempdir(), "faster-whisper-models"),
        modelo.replace("/", "--"),
    )
    if all(os.path.isfile(os.path.join(cache, nombre)) for nombre in _ARCHIVOS_WHISPER):
        return cache
    repo = modelo if "/" in modelo else f"Systran/faster-whisper-{modelo}"
    os.makedirs(cache, exist_ok=True)
    verify = ai_config.ai_ssl_verify()
    with httpx.Client(timeout=300.0, verify=verify, follow_redirects=True) as client:
        for nombre in _ARCHIVOS_WHISPER:
            dest = os.path.join(cache, nombre)
            if os.path.isfile(dest):
                continue
            url = f"https://huggingface.co/{repo}/resolve/main/{nombre}"
            logger.info("Descargando Whisper local %s (%s)", modelo, nombre)
            try:
                with client.stream("GET", url) as response:
                    response.raise_for_status()
                    parcial = dest + ".part"
                    with open(parcial, "wb") as fh:
                        for chunk in response.iter_bytes(1024 * 1024):
                            fh.write(chunk)
                    os.replace(parcial, dest)
            except Exception as exc:
                logger.error("Error bajando Whisper %s: %s", nombre, type(exc).__name__)
                raise TranscripcionError(
                    "No se pudo descargar el modelo Whisper local. "
                    "Revisá la red o poné el modelo en AI_STT_MODEL_DIR."
                ) from exc
    return cache


def transcribir_audio(
    audio: bytes,
    mime_type: str,
    proveedor: str | None = None,
) -> str:
    """Devuelve solo el texto transcripto. El audio no se guarda."""
    if not audio:
        raise TranscripcionError("Audio vacío")

    backend = ai_config.resolver_stt_provider(proveedor)
    logger.info("STT %s (%d bytes, %s)", backend, len(audio), mime_type)
    if backend == "mock":
        texto = ai_config.ai_stt_mock_texto()
    elif backend == "local":
        texto = _transcribir_local(audio, mime_type)
    elif backend == "gemini":
        texto = _transcribir_gemini(audio, mime_type)
    else:
        texto = _transcribir_openai(audio, mime_type)
    logger.info("STT texto: %s", texto)
    return texto


def _transcribir_local(audio: bytes, mime_type: str) -> str:
    """Whisper en esta máquina: servidor OpenAI-compatible o faster-whisper."""
    base_url = ai_config.ai_stt_base_url()
    if base_url:
        return _transcribir_openai_compatible(
            audio,
            mime_type,
            base_url=base_url,
            api_key=ai_config.openai_api_key() or "local",
            model=ai_config.ai_stt_local_model(),
        )
    return _transcribir_faster_whisper(audio, mime_type)


def _transcribir_faster_whisper(audio: bytes, mime_type: str) -> str:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise TranscripcionError(
            "No hay transcripción local. Instalá faster-whisper "
            "(docker compose exec backend pip install faster-whisper) "
            "o levantá un Whisper en AI_STT_BASE_URL."
        ) from exc

    global _whisper_local
    if _whisper_local is None:
        modelo = _cache_modelo_whisper(ai_config.ai_stt_local_model())
        logger.info("Cargando Whisper local (%s)", modelo)
        _whisper_local = WhisperModel(modelo, device="cpu", compute_type="int8")

    try:
        muestras = _audio_a_float32(audio, mime_type)
        segmentos, _info = _whisper_local.transcribe(muestras, language="es")
        texto = " ".join(seg.text.strip() for seg in segmentos if seg.text).strip()
    except TranscripcionError:
        raise
    except Exception as exc:
        logger.error("Error STT local: %s", exc)
        raise TranscripcionError(f"Whisper local no pudo transcribir el audio: {exc}") from exc
    if not texto:
        raise TranscripcionError("Whisper local devolvió una transcripción vacía")
    return texto


def _audio_a_float32(audio: bytes, mime_type: str):
    """ffmpeg → WAV 16 kHz mono. Evita PyAV 19, que rompe faster-whisper."""
    extension = _EXT_WHISPER.get(_mime_base(mime_type), "ogg")
    with tempfile.NamedTemporaryFile(suffix=f".{extension}", delete=False) as tmp:
        tmp.write(audio)
        origen = tmp.name
    destino = origen + ".16k.wav"
    try:
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", origen, "-ac", "1", "-ar", "16000", destino],
                check=True,
                capture_output=True,
            )
        except FileNotFoundError as exc:
            raise TranscripcionError(
                "Falta ffmpeg en el contenedor para transcribir audio local."
            ) from exc
        except subprocess.CalledProcessError as exc:
            logger.error("ffmpeg STT: %s", exc.stderr[-200:] if exc.stderr else exc)
            raise TranscripcionError("No se pudo leer el audio para transcribirlo.") from exc
        with wave.open(destino, "rb") as wav:
            frames = wav.readframes(wav.getnframes())
        return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    finally:
        for ruta in (origen, destino):
            try:
                os.unlink(ruta)
            except OSError:
                pass


def _transcribir_openai_compatible(
    audio: bytes,
    mime_type: str,
    *,
    base_url: str,
    api_key: str,
    model: str,
) -> str:
    url = f"{base_url}/audio/transcriptions"
    headers = {"Authorization": f"Bearer {api_key}"}
    mime = _mime_base(mime_type)
    extension = _EXT_WHISPER.get(mime, "ogg")
    files = {"file": (f"audio.{extension}", audio, mime)}
    data = {"model": model, "language": "es"}
    try:
        with httpx.Client(timeout=120.0, verify=ai_config.ai_ssl_verify()) as client:
            response = client.post(url, headers=headers, files=files, data=data)
            response.raise_for_status()
            texto = str(response.json().get("text") or "").strip()
    except Exception as exc:
        logger.error("Error STT %s: %s", base_url.split("?")[0], type(exc).__name__)
        raise TranscripcionError("No se pudo transcribir el audio. Probá de nuevo.") from exc
    if not texto:
        raise TranscripcionError("La transcripción vino vacía")
    return texto


def _transcribir_gemini(audio: bytes, mime_type: str) -> str:
    url = (
        f"{ai_config.ai_gemini_native_url()}/models/"
        f"{ai_config.openai_model()}:generateContent"
    )
    mime = _MIME_GEMINI.get(_mime_base(mime_type), "audio/ogg")
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": _PROMPT_TRANSCRIPCION},
                    {
                        "inline_data": {
                            "mime_type": mime,
                            "data": base64.b64encode(audio).decode("ascii"),
                        }
                    },
                ]
            }
        ]
    }
    # La API nativa de Gemini usa ?key=, no Bearer del endpoint OpenAI-compatible.
    params = {"key": ai_config.openai_api_key()}
    ultimo_error = None
    data = None
    for intento in range(3):
        try:
            with httpx.Client(timeout=60.0, verify=ai_config.ai_ssl_verify()) as client:
                response = client.post(url, params=params, json=payload)
                if response.status_code in {429, 500, 502, 503, 504} and intento < 2:
                    logger.warning("STT Gemini %s, reintento %s", response.status_code, intento + 1)
                    time.sleep(1.0 * (2**intento))
                    continue
                response.raise_for_status()
                data = response.json()
            break
        except Exception as exc:
            ultimo_error = exc
            logger.error("Error STT Gemini: %s", type(exc).__name__)
            if intento < 2:
                time.sleep(1.0 * (2**intento))
                continue
            raise TranscripcionError(
                "Gemini no pudo transcribir el audio. Probá de nuevo en un momento."
            ) from exc
    if data is None:
        raise TranscripcionError(
            "Gemini no pudo transcribir el audio. Probá de nuevo en un momento."
        ) from ultimo_error
    partes = data["candidates"][0]["content"]["parts"]
    texto = "".join(p.get("text", "") for p in partes).strip()
    if not texto:
        raise TranscripcionError("Gemini devolvió una transcripción vacía")
    return texto


def _transcribir_openai(audio: bytes, mime_type: str) -> str:
    key = ai_config.openai_api_key()
    if not key:
        raise TranscripcionError("Falta OPENAI_API_KEY para transcribir con Whisper en la nube")
    return _transcribir_openai_compatible(
        audio,
        mime_type,
        base_url=ai_config.ai_base_url(),
        api_key=key,
        model=ai_config.ai_stt_model(),
    )
