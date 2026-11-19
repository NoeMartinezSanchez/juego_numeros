import asyncio
import json
import os
import sqlite3

import pytest
import stripe
from fastapi.testclient import TestClient

import backend.billing as billing
import backend.db as db
from backend.auth import usuario_actual
from backend.main import app

cliente = TestClient(app)


@pytest.fixture(autouse=True)
def base_datos(tmp_path, monkeypatch):
    ruta = tmp_path / "melate_test.db"
    monkeypatch.setattr(db, "PATH_BD", ruta)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_dummy")
    monkeypatch.setenv("STRIPE_PRICE_MENSUAL", "price_mensual_dummy")
    monkeypatch.setenv("STRIPE_PRICE_INDIVIDUAL", "price_individual_dummy")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_dummy")
    asyncio.run(db.inicializar_bd())
    asyncio.run(billing.inicializar_suscripciones())
    yield ruta
    app.dependency_overrides.clear()


@pytest.fixture
def sesion(base_datos):
    usuario = asyncio.run(
        db.guardar_usuario("sub-test", "test@example.com", "Test")
    )
    app.dependency_overrides[usuario_actual] = lambda: {
        "id": usuario["id"],
        "email": usuario["email"],
    }
    yield usuario
    app.dependency_overrides.pop(usuario_actual, None)


def test_estado_sin_cookie_devuelve_401():
    respuesta = cliente.get("/api/billing/estado")
    assert respuesta.status_code == 401
    assert respuesta.json() == {"error": "No autenticado"}


def test_checkout_mensual_sin_cookie_devuelve_401():
    respuesta = cliente.post("/api/billing/checkout-mensual")
    assert respuesta.status_code == 401
    assert respuesta.json() == {"error": "No autenticado"}


def test_checkout_mensual_con_sesion_devuelve_url(sesion, monkeypatch):
    llamadas = []

    class SesionFalsa:
        url = "https://checkout.stripe.com/test"

    def crear(**kwargs):
        llamadas.append(kwargs)
        return SesionFalsa()

    monkeypatch.setattr(stripe.checkout.Session, "create", crear)
    respuesta = cliente.post("/api/billing/checkout-mensual")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"url": "https://checkout.stripe.com/test"}
    assert llamadas[0]["mode"] == "subscription"
    assert llamadas[0]["client_reference_id"] == str(sesion["id"])
    assert llamadas[0]["customer_email"] == sesion["email"]


def test_tickets_sin_suscripcion_devuelve_402(sesion):
    respuesta = cliente.post("/api/tickets", json={"n": 1})
    assert respuesta.status_code == 402
    assert respuesta.json() == {
        "error": "Se requiere suscripción activa o generación individual"
    }


def test_tickets_con_suscripcion_activa_devuelve_200(sesion):
    asyncio.run(
        billing.guardar_suscripcion(
            sesion["id"],
            "cus_test",
            "sub_test",
            "active",
            "2100-01-01T00:00:00+00:00",
        )
    )
    respuesta = cliente.post("/api/tickets", json={"n": 1})
    assert respuesta.status_code == 200
    assert len(respuesta.json()["tickets"]) == 1


def test_webhook_firma_invalida_devuelve_400():
    respuesta = cliente.post(
        "/api/webhooks/stripe",
        content=b'{"id": "evt_test"}',
        headers={"stripe-signature": "t=1,v1=invalida"},
    )
    assert respuesta.status_code == 400


def test_webhook_checkout_completado_inserta_suscripcion(
    sesion, base_datos, monkeypatch
):
    evento = {
        "id": "evt_test",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "mode": "subscription",
                "client_reference_id": str(sesion["id"]),
                "customer": "cus_test",
                "subscription": "sub_test",
            }
        },
    }
    monkeypatch.setattr(
        stripe.Webhook, "construct_event", lambda *args, **kwargs: evento
    )
    monkeypatch.setattr(
        stripe.Subscription,
        "retrieve",
        lambda *args, **kwargs: {
            "id": "sub_test",
            "status": "active",
            "current_period_end": 4102444800,
        },
    )
    primera = cliente.post(
        "/api/webhooks/stripe",
        content=b"{}",
        headers={"stripe-signature": "t=1,v1=test"},
    )
    segunda = cliente.post(
        "/api/webhooks/stripe",
        content=b"{}",
        headers={"stripe-signature": "t=1,v1=test"},
    )
    assert primera.status_code == 200
    assert segunda.status_code == 200
    assert primera.json() == {"status": "ok"}
    conexion = sqlite3.connect(str(base_datos))
    fila = conexion.execute(
        """
        SELECT user_id, stripe_customer_id, stripe_subscription_id, status,
               current_period_end
        FROM suscripciones
        WHERE stripe_subscription_id = ?
        """,
        ("sub_test",),
    ).fetchone()
    total = conexion.execute(
        "SELECT COUNT(*) FROM suscripciones WHERE stripe_subscription_id = ?",
        ("sub_test",),
    ).fetchone()[0]
    conexion.close()
    assert fila is not None
    assert total == 1
    assert fila[0] == sesion["id"]
    assert fila[1] == "cus_test"
    assert fila[2] == "sub_test"
    assert fila[3] == "active"
    assert fila[4] is not None


def test_webhook_firma_valida_inserta_suscripcion(
    sesion, base_datos, monkeypatch
):
    evento = {
        "id": "evt_firma_valida",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "mode": "subscription",
                "client_reference_id": str(sesion["id"]),
                "customer": "cus_firma",
                "subscription": "sub_firma",
            }
        },
    }
    payload = json.dumps(evento)
    firma = stripe.WebhookSignature.generate_signature_header(
        payload, os.getenv("STRIPE_WEBHOOK_SECRET")
    )
    suscripcion = stripe.Subscription.construct_from(
        {
            "id": "sub_firma",
            "status": "active",
            "current_period_end": 4102444800,
        },
        "sk_test_dummy",
    )
    monkeypatch.setattr(
        stripe.Subscription,
        "retrieve",
        lambda *args, **kwargs: suscripcion,
    )
    respuesta = cliente.post(
        "/api/webhooks/stripe",
        content=payload.encode("utf-8"),
        headers={"stripe-signature": firma},
    )
    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "ok"}
    conexion = sqlite3.connect(str(base_datos))
    fila = conexion.execute(
        """
        SELECT user_id, stripe_customer_id, stripe_subscription_id, status,
               current_period_end
        FROM suscripciones
        WHERE stripe_subscription_id = ?
        """,
        ("sub_firma",),
    ).fetchone()
    conexion.close()
    assert fila is not None
    assert fila[0] == sesion["id"]
    assert fila[1] == "cus_firma"
    assert fila[2] == "sub_firma"
    assert fila[3] == "active"
    assert fila[4] is not None


def test_webhook_pago_individual_inserta_credito_idempotente(
    sesion, base_datos
):
    evento = {
        "id": "evt_pago_individual",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_pago_individual",
                "mode": "payment",
                "payment_status": "paid",
                "client_reference_id": str(sesion["id"]),
                "customer": "cus_pago_individual",
            }
        },
    }
    payload = json.dumps(evento)
    firma = stripe.WebhookSignature.generate_signature_header(
        payload, os.getenv("STRIPE_WEBHOOK_SECRET")
    )
    primera = cliente.post(
        "/api/webhooks/stripe",
        content=payload.encode("utf-8"),
        headers={"stripe-signature": firma},
    )
    segunda = cliente.post(
        "/api/webhooks/stripe",
        content=payload.encode("utf-8"),
        headers={"stripe-signature": firma},
    )
    assert primera.status_code == 200
    assert segunda.status_code == 200
    assert primera.json() == {"status": "ok"}
    conexion = sqlite3.connect(str(base_datos))
    total = conexion.execute(
        """
        SELECT COUNT(*)
        FROM generaciones_individuales
        WHERE stripe_session_id = ?
        """,
        ("cs_test_pago_individual",),
    ).fetchone()[0]
    fila = conexion.execute(
        """
        SELECT user_id, usado
        FROM generaciones_individuales
        WHERE stripe_session_id = ?
        """,
        ("cs_test_pago_individual",),
    ).fetchone()
    conexion.close()
    assert total == 1
    assert fila == (sesion["id"], 0)


def test_tickets_con_credito_individual_permite_uno(sesion, base_datos):
    asyncio.run(
        billing.registrar_pago_individual(
            sesion["id"],
            "cs_test_credito_uno",
            "cus_credito",
        )
    )
    primera = cliente.post("/api/tickets", json={"n": 1})
    segunda = cliente.post("/api/tickets", json={"n": 1})
    assert primera.status_code == 200
    assert len(primera.json()["tickets"]) == 1
    assert segunda.status_code == 402
    assert segunda.json() == {
        "error": "Se requiere suscripción activa o generación individual"
    }
    conexion = sqlite3.connect(str(base_datos))
    usado = conexion.execute(
        """
        SELECT usado
        FROM generaciones_individuales
        WHERE stripe_session_id = ?
        """,
        ("cs_test_credito_uno",),
    ).fetchone()[0]
    conexion.close()
    assert usado == 1


def test_tickets_con_credito_individual_rechaza_n_mayor(sesion, base_datos):
    asyncio.run(
        billing.registrar_pago_individual(
            sesion["id"],
            "cs_test_credito_dos",
            "cus_credito",
        )
    )
    respuesta = cliente.post("/api/tickets", json={"n": 2})
    assert respuesta.status_code == 400
    assert respuesta.json() == {
        "error": "La generación individual permite solo 1 boleto"
    }
    conexion = sqlite3.connect(str(base_datos))
    usado = conexion.execute(
        """
        SELECT usado
        FROM generaciones_individuales
        WHERE stripe_session_id = ?
        """,
        ("cs_test_credito_dos",),
    ).fetchone()[0]
    conexion.close()
    assert usado == 0


def test_estado_incluye_creditos_individuales(sesion, base_datos):
    asyncio.run(
        billing.registrar_pago_individual(
            sesion["id"],
            "cs_test_estado_credito",
            "cus_estado",
        )
    )
    respuesta = cliente.get("/api/billing/estado")
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["suscripcion_activa"] is False
    assert datos["creditos_individuales"] == 1
