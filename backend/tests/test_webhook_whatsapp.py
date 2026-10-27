"""Webhook de WhatsApp: solo procesa lo que viene firmado por Meta; y la SECRET_KEY es
obligatoria en producción."""

import hashlib
import hmac
import json
from unittest.mock import patch

import pytest

from core import auth

SECRETO = "app-secret-de-prueba"
MENSAJE = {
    "entry": [
        {
            "changes": [
                {
                    "value": {
                        "messages": [
                            {"from": "5491100000000", "type": "text", "text": {"body": "si"}}
                        ]
                    }
                }
            ]
        }
    ]
}


def _firmar(cuerpo: bytes, secreto: str = SECRETO) -> str:
    return "sha256=" + hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()


@pytest.fixture
def despachados():
    with patch("api.whatsapp._despachar") as despachar:
        yield despachar


def _post(client, cuerpo: bytes, firma: str | None):
    headers = {"Content-Type": "application/json"}
    if firma is not None:
        headers["X-Hub-Signature-256"] = firma
    return client.post("/webhook/whatsapp", content=cuerpo, headers=headers)


def test_un_mensaje_firmado_por_meta_se_procesa(client, monkeypatch, despachados):
    monkeypatch.setenv("WHATSAPP_APP_SECRET", SECRETO)
    cuerpo = json.dumps(MENSAJE).encode()

    respuesta = _post(client, cuerpo, _firmar(cuerpo))

    assert respuesta.status_code == 200
    despachados.assert_called_once()
    assert despachados.call_args.args[0]["from"] == "5491100000000"


@pytest.mark.parametrize(
    "firma",
    [None, "sha256=" + "0" * 64, _firmar(b"otro cuerpo"), _firmar(b"x", secreto="otro-secreto")],
    ids=["sin-firma", "firma-falsa", "firma-de-otro-cuerpo", "firma-con-otro-secreto"],
)
def test_un_mensaje_sin_firma_valida_no_se_procesa(client, monkeypatch, despachados, firma):
    """Lo que mandaría alguien haciéndose pasar por una escuela."""
    monkeypatch.setenv("WHATSAPP_APP_SECRET", SECRETO)

    respuesta = _post(client, json.dumps(MENSAJE).encode(), firma)

    assert respuesta.status_code == 403
    despachados.assert_not_called()


def test_sin_app_secret_configurado_se_rechaza_todo(client, monkeypatch, despachados):
    monkeypatch.delenv("WHATSAPP_APP_SECRET", raising=False)
    cuerpo = json.dumps(MENSAJE).encode()

    assert _post(client, cuerpo, _firmar(cuerpo, secreto="")).status_code == 403
    despachados.assert_not_called()


def _verificar(client, token):
    return client.get(
        "/webhook/whatsapp",
        params={"hub.mode": "subscribe", "hub.verify_token": token, "hub.challenge": "123"},
    )


def test_la_verificacion_del_webhook_pide_el_token_configurado(client, monkeypatch):
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "token-propio")

    ok = _verificar(client, "token-propio")
    assert ok.status_code == 200 and ok.text == "123"
    assert _verificar(client, "infrabot-verify-token").status_code == 403


def test_sin_token_configurado_la_verificacion_falla(client, monkeypatch):
    monkeypatch.delenv("WHATSAPP_VERIFY_TOKEN", raising=False)

    assert _verificar(client, "").status_code == 403
    assert _verificar(client, "infrabot-verify-token").status_code == 403


# --- SECRET_KEY ------------------------------------------------------------------------


@pytest.mark.parametrize("clave", ["", auth.CLAVE_DE_DESARROLLO], ids=["vacia", "la-de-desarrollo"])
def test_en_produccion_sin_secret_key_propia_no_arranca(monkeypatch, clave):
    monkeypatch.setenv("COOKIE_SECURE", "true")
    monkeypatch.setenv("SECRET_KEY", clave)

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        auth._secret_key()


def test_en_produccion_usa_la_secret_key_configurada(monkeypatch):
    monkeypatch.setenv("COOKIE_SECURE", "true")
    monkeypatch.setenv("SECRET_KEY", "una-clave-larga-y-propia")

    assert auth._secret_key() == "una-clave-larga-y-propia"


def test_en_desarrollo_sin_secret_key_usa_la_de_desarrollo(monkeypatch):
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("SECRET_KEY", "")

    assert auth._secret_key() == auth.CLAVE_DE_DESARROLLO
