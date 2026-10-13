from core.ai.factory import reset_llm_provider_cache
from core.dependencies import get_current_admin, get_current_user
from main import app
from services.ai.stt import TranscripcionError, transcribir_audio


def test_transcribir_audio_mock_devuelve_texto(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setenv("AI_STT_PROVIDER", "mock")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    texto = transcribir_audio(b"bytes-de-audio", "audio/ogg")
    assert len(texto) > 10


def test_transcribir_audio_vacio_falla():
    try:
        transcribir_audio(b"", "audio/ogg")
    except TranscripcionError as exc:
        assert "vacío" in str(exc).lower()
    else:
        raise AssertionError("esperaba TranscripcionError")


def _autenticar_como_admin():
    admin = app.dependency_overrides[get_current_admin]()
    app.dependency_overrides[get_current_user] = lambda: admin


def test_endpoint_transcribir_mock(client, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setenv("AI_STT_PROVIDER", "mock")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    reset_llm_provider_cache()
    _autenticar_como_admin()
    try:
        respuesta = client.post(
            "/ai/transcribir",
            files={"archivo": ("nota.ogg", b"audio-falso", "audio/ogg")},
        )
        assert respuesta.status_code == 200
        body = respuesta.json()
        assert body["texto"]
        assert body["proveedor"] == "mock"
        assert body["mime_type"].startswith("audio/")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        reset_llm_provider_cache()


def test_cache_modelo_whisper_reusa_directorio_completo(tmp_path, monkeypatch):
    import services.ai.stt as stt_mod

    for nombre in stt_mod._ARCHIVOS_WHISPER:
        (tmp_path / nombre).write_text("ok")
    monkeypatch.setenv("AI_STT_MODEL_DIR", str(tmp_path.parent))
    assert stt_mod._cache_modelo_whisper(tmp_path.name) == str(tmp_path)


def test_transcribir_override_mock_ignora_provider_local(monkeypatch):
    monkeypatch.setenv("AI_STT_PROVIDER", "local")
    texto = transcribir_audio(b"bytes-de-audio", "audio/ogg", proveedor="mock")
    assert len(texto) > 10


def test_local_sin_whisper_no_usa_texto_falso(monkeypatch):
    import services.ai.stt as stt_mod

    monkeypatch.setenv("AI_STT_PROVIDER", "local")
    monkeypatch.delenv("AI_STT_BASE_URL", raising=False)
    def _sin_local(*_args, **_kwargs):
        raise TranscripcionError("No hay transcripción local")

    monkeypatch.setattr(stt_mod, "_transcribir_faster_whisper", _sin_local)
    try:
        transcribir_audio(b"bytes-de-audio", "audio/ogg")
    except TranscripcionError as exc:
        assert "local" in str(exc).lower()
    else:
        raise AssertionError("sin Whisper local no debería inventar un texto")


def test_endpoint_transcribir_rechaza_no_audio(client):
    _autenticar_como_admin()
    try:
        respuesta = client.post(
            "/ai/transcribir",
            files={"archivo": ("foto.jpg", b"no-es-audio", "image/jpeg")},
        )
        assert respuesta.status_code == 400
    finally:
        app.dependency_overrides.pop(get_current_user, None)
