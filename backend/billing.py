import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request

from backend.auth import usuario_actual
from backend.db import conectar

logger = logging.getLogger(__name__)

SUCCESS_URL = "http://localhost:5173?checkout=success"
CANCEL_URL = "http://localhost:5173?checkout=cancel"
PORTAL_URL = "http://localhost:5173"


@asynccontextmanager
async def _lifespan(app):
    await inicializar_suscripciones()
    yield


billing_router = APIRouter(lifespan=_lifespan)
webhook_router = APIRouter()


def _configuracion_checkout_mensual():
    return bool(
        os.getenv("STRIPE_SECRET_KEY") and os.getenv("STRIPE_PRICE_MENSUAL")
    )


def _configuracion_checkout_individual():
    return bool(
        os.getenv("STRIPE_SECRET_KEY") and os.getenv("STRIPE_PRICE_INDIVIDUAL")
    )


def _configuracion_portal():
    return bool(os.getenv("STRIPE_SECRET_KEY"))


def _configuracion_webhook():
    return bool(
        os.getenv("STRIPE_SECRET_KEY") and os.getenv("STRIPE_WEBHOOK_SECRET")
    )


async def inicializar_suscripciones():
    async with conectar() as bd:
        await bd.execute(
            """
            CREATE TABLE IF NOT EXISTS suscripciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                stripe_customer_id TEXT,
                stripe_subscription_id TEXT,
                status TEXT NOT NULL,
                current_period_end TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES usuarios(id)
            )
            """
        )
        await bd.execute(
            "DROP INDEX IF EXISTS idx_suscripciones_subscription"
        )
        await bd.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_suscripciones_subscription
            ON suscripciones(stripe_subscription_id)
            """
        )
        await bd.execute(
            """
            CREATE TABLE IF NOT EXISTS generaciones_individuales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                stripe_session_id TEXT UNIQUE NOT NULL,
                stripe_customer_id TEXT,
                usado INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                usado_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES usuarios(id)
            )
            """
        )
        await bd.commit()


def _como_dict(valor):
    if hasattr(valor, "to_dict"):
        return valor.to_dict()
    return valor


def _id_stripe(valor):
    if valor is None:
        return None
    if isinstance(valor, str):
        return valor
    if isinstance(valor, dict):
        return valor.get("id") or str(valor)
    return getattr(valor, "id", str(valor))


def _iso_desde_timestamp(valor):
    if valor is None:
        return None
    if isinstance(valor, datetime):
        if valor.tzinfo is None:
            valor = valor.replace(tzinfo=timezone.utc)
        return valor.astimezone(timezone.utc).isoformat()
    return datetime.fromtimestamp(int(valor), timezone.utc).isoformat()


def _items_suscripcion(suscripcion):
    items = suscripcion.get("items")
    if items is None:
        return []
    if isinstance(items, dict):
        return items.get("data") or []
    return getattr(items, "data", []) or []


def _period_end_suscripcion(suscripcion):
    valor = suscripcion.get("current_period_end")
    if valor is None:
        items = _items_suscripcion(suscripcion)
        if items:
            valor = items[0].get("current_period_end")
    return _iso_desde_timestamp(valor)


def _esta_activa(suscripcion):
    if not suscripcion:
        return False
    if suscripcion["status"] not in ("active", "trialing"):
        return False
    fin = suscripcion["current_period_end"]
    if not fin:
        return False
    try:
        fin_dt = datetime.fromisoformat(fin)
    except ValueError:
        return False
    if fin_dt.tzinfo is None:
        fin_dt = fin_dt.replace(tzinfo=timezone.utc)
    return fin_dt > datetime.now(timezone.utc)


async def obtener_ultima_suscripcion(usuario_id):
    async with conectar() as bd:
        cursor = await bd.execute(
            """
            SELECT id, user_id, stripe_customer_id, stripe_subscription_id,
                   status, current_period_end, created_at
            FROM suscripciones
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (usuario_id,),
        )
        fila = await cursor.fetchone()
        if fila is None:
            return None
        return dict(fila)


async def guardar_suscripcion(
    user_id,
    stripe_customer_id,
    stripe_subscription_id,
    status,
    current_period_end,
):
    async with conectar() as bd:
        await bd.execute(
            """
            INSERT INTO suscripciones (
                user_id, stripe_customer_id, stripe_subscription_id,
                status, current_period_end
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(stripe_subscription_id) DO UPDATE SET
                user_id = excluded.user_id,
                stripe_customer_id = excluded.stripe_customer_id,
                status = excluded.status,
                current_period_end = excluded.current_period_end
            """,
            (
                user_id,
                stripe_customer_id,
                stripe_subscription_id,
                status,
                current_period_end,
            ),
        )
        await bd.commit()


async def actualizar_suscripcion_por_subscription(
    stripe_subscription_id, status, current_period_end=None
):
    async with conectar() as bd:
        if current_period_end is None:
            cursor = await bd.execute(
                "UPDATE suscripciones SET status = ? WHERE stripe_subscription_id = ?",
                (status, stripe_subscription_id),
            )
        else:
            cursor = await bd.execute(
                """
                UPDATE suscripciones
                SET status = ?, current_period_end = ?
                WHERE stripe_subscription_id = ?
                """,
                (status, current_period_end, stripe_subscription_id),
            )
        await bd.commit()
        return cursor.rowcount


async def contar_creditos_individuales(usuario_id):
    async with conectar() as bd:
        cursor = await bd.execute(
            """
            SELECT COUNT(*)
            FROM generaciones_individuales
            WHERE user_id = ? AND usado = 0
            """,
            (usuario_id,),
        )
        fila = await cursor.fetchone()
        return int(fila[0])


async def registrar_pago_individual(
    user_id, stripe_session_id, stripe_customer_id=None
):
    async with conectar() as bd:
        await bd.execute(
            """
            INSERT INTO generaciones_individuales (
                user_id, stripe_session_id, stripe_customer_id
            )
            VALUES (?, ?, ?)
            ON CONFLICT(stripe_session_id) DO NOTHING
            """,
            (user_id, stripe_session_id, stripe_customer_id),
        )
        await bd.commit()


async def consumir_credito_individual(usuario_id):
    async with conectar() as bd:
        cursor = await bd.execute(
            """
            UPDATE generaciones_individuales
            SET usado = 1, usado_at = CURRENT_TIMESTAMP
            WHERE id = (
                SELECT id
                FROM generaciones_individuales
                WHERE user_id = ? AND usado = 0
                ORDER BY id ASC
                LIMIT 1
            )
            AND usado = 0
            """,
            (usuario_id,),
        )
        await bd.commit()
        return cursor.rowcount > 0


async def acceso_generacion(usuario=Depends(usuario_actual)):
    suscripcion = await obtener_ultima_suscripcion(usuario["id"])
    if _esta_activa(suscripcion):
        return {
            "tipo": "suscripcion",
            "usuario": usuario,
            "creditos": None,
        }
    creditos = await contar_creditos_individuales(usuario["id"])
    if creditos > 0:
        return {
            "tipo": "individual",
            "usuario": usuario,
            "creditos": creditos,
        }
    raise HTTPException(
        status_code=402,
        detail="Se requiere suscripción activa o generación individual",
    )


async def suscripcion_activa(usuario=Depends(usuario_actual)):
    suscripcion = await obtener_ultima_suscripcion(usuario["id"])
    if not _esta_activa(suscripcion):
        raise HTTPException(
            status_code=402, detail="Se requiere suscripción activa"
        )
    return suscripcion


@billing_router.post("/checkout-mensual")
async def checkout_mensual(usuario=Depends(usuario_actual)):
    if not _configuracion_checkout_mensual():
        raise HTTPException(
            status_code=500, detail="Configuración Stripe incompleta"
        )
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[
                {
                    "price": os.getenv("STRIPE_PRICE_MENSUAL"),
                    "quantity": 1,
                }
            ],
            client_reference_id=str(usuario["id"]),
            customer_email=usuario["email"],
            success_url=SUCCESS_URL,
            cancel_url=CANCEL_URL,
        )
        return {"url": session.url}
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail="Error de Stripe: " + str(e))


@billing_router.post("/checkout-individual")
async def checkout_individual(usuario=Depends(usuario_actual)):
    if not _configuracion_checkout_individual():
        raise HTTPException(
            status_code=500, detail="Configuración Stripe incompleta"
        )
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[
                {
                    "price": os.getenv("STRIPE_PRICE_INDIVIDUAL"),
                    "quantity": 1,
                }
            ],
            client_reference_id=str(usuario["id"]),
            customer_email=usuario["email"],
            success_url=SUCCESS_URL,
            cancel_url=CANCEL_URL,
        )
        return {"url": session.url}
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail="Error de Stripe: " + str(e))


@billing_router.post("/portal")
async def portal(usuario=Depends(usuario_actual)):
    if not _configuracion_portal():
        raise HTTPException(
            status_code=500, detail="Configuración Stripe incompleta"
        )
    suscripcion = await obtener_ultima_suscripcion(usuario["id"])
    if not suscripcion or not suscripcion["stripe_customer_id"]:
        raise HTTPException(
            status_code=400,
            detail="No tienes una suscripción activa para gestionar",
        )
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
    try:
        session = stripe.billing_portal.Session.create(
            customer=suscripcion["stripe_customer_id"],
            return_url=PORTAL_URL,
        )
        return {"url": session.url}
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail="Error de Stripe: " + str(e))


@billing_router.get("/estado")
async def estado(usuario=Depends(usuario_actual)):
    suscripcion = await obtener_ultima_suscripcion(usuario["id"])
    creditos = await contar_creditos_individuales(usuario["id"])
    if suscripcion is None:
        return {
            "suscripcion_activa": False,
            "status": None,
            "current_period_end": None,
            "creditos_individuales": creditos,
        }
    return {
        "suscripcion_activa": _esta_activa(suscripcion),
        "status": suscripcion["status"],
        "current_period_end": suscripcion["current_period_end"],
        "creditos_individuales": creditos,
    }


async def _procesar_checkout(evento):
    sesion = evento["data"]["object"]
    modo = sesion.get("mode")
    if modo == "payment":
        await _procesar_pago_individual(evento, sesion)
        return
    if modo != "subscription":
        return
    subscription_id = _id_stripe(sesion.get("subscription"))
    if not subscription_id:
        logger.warning(
            "checkout.session.completed sin subscription_id: %s",
            evento.get("id"),
        )
        return
    try:
        user_id = int(sesion.get("client_reference_id"))
    except (TypeError, ValueError):
        logger.warning(
            "checkout.session.completed con client_reference_id inválido: %s",
            evento.get("id"),
        )
        return
    customer_id = _id_stripe(sesion.get("customer"))
    suscripcion = _como_dict(stripe.Subscription.retrieve(subscription_id))
    period_end = _period_end_suscripcion(suscripcion)
    await guardar_suscripcion(
        user_id, customer_id, subscription_id, "active", period_end
    )


async def _procesar_pago_individual(evento, sesion):
    session_id = sesion.get("id")
    if not session_id:
        logger.warning(
            "checkout.session.completed de pago sin session_id: %s",
            evento.get("id"),
        )
        return
    if sesion.get("payment_status") != "paid":
        logger.warning(
            "checkout.session.completed de pago no pagado: %s",
            evento.get("id"),
        )
        return
    try:
        user_id = int(sesion.get("client_reference_id"))
    except (TypeError, ValueError):
        logger.warning(
            "checkout.session.completed de pago con client_reference_id inválido: %s",
            evento.get("id"),
        )
        return
    customer_id = _id_stripe(sesion.get("customer"))
    await registrar_pago_individual(user_id, session_id, customer_id)


async def _procesar_suscripcion_actualizada(evento):
    suscripcion = evento["data"]["object"]
    subscription_id = _id_stripe(suscripcion.get("id"))
    if not subscription_id:
        logger.warning(
            "customer.subscription.updated sin subscription_id: %s",
            evento.get("id"),
        )
        return
    status = suscripcion.get("status")
    if not status:
        logger.warning(
            "customer.subscription.updated sin status: %s",
            evento.get("id"),
        )
        return
    period_end = _period_end_suscripcion(suscripcion)
    actualizadas = await actualizar_suscripcion_por_subscription(
        subscription_id, status, period_end
    )
    if not actualizadas:
        logger.warning(
            "customer.subscription.updated sin fila local: %s",
            subscription_id,
        )


async def _procesar_suscripcion_eliminada(evento):
    suscripcion = evento["data"]["object"]
    subscription_id = _id_stripe(suscripcion.get("id"))
    if not subscription_id:
        logger.warning(
            "customer.subscription.deleted sin subscription_id: %s",
            evento.get("id"),
        )
        return
    period_end = _period_end_suscripcion(suscripcion)
    actualizadas = await actualizar_suscripcion_por_subscription(
        subscription_id, "canceled", period_end
    )
    if not actualizadas:
        logger.warning(
            "customer.subscription.deleted sin fila local: %s",
            subscription_id,
        )


async def _procesar_pago_fallido(evento):
    factura = evento["data"]["object"]
    subscription_id = _id_stripe(factura.get("subscription"))
    if not subscription_id:
        logger.warning(
            "invoice.payment_failed sin subscription_id: %s",
            evento.get("id"),
        )
        return
    actualizadas = await actualizar_suscripcion_por_subscription(
        subscription_id, "past_due"
    )
    if not actualizadas:
        logger.warning(
            "invoice.payment_failed sin fila local: %s",
            subscription_id,
        )


@webhook_router.post("/api/webhooks/stripe")
async def webhook_stripe(request: Request):
    if not _configuracion_webhook():
        raise HTTPException(
            status_code=500, detail="Configuración Stripe incompleta"
        )
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    if not sig_header:
        raise HTTPException(status_code=400, detail="Firma inválida")
    try:
        evento = stripe.Webhook.construct_event(
            payload, sig_header, os.getenv("STRIPE_WEBHOOK_SECRET")
        )
        evento = _como_dict(evento)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Firma inválida")
    except Exception:
        raise HTTPException(status_code=400, detail="Firma inválida")
    tipo = evento["type"]
    event_id = evento["id"]
    logger.info("Evento Stripe recibido: %s %s", tipo, event_id)
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
    try:
        if tipo == "checkout.session.completed":
            await _procesar_checkout(evento)
        elif tipo == "customer.subscription.updated":
            await _procesar_suscripcion_actualizada(evento)
        elif tipo == "customer.subscription.deleted":
            await _procesar_suscripcion_eliminada(evento)
        elif tipo == "invoice.payment_failed":
            await _procesar_pago_fallido(evento)
    except stripe.error.StripeError as e:
        logger.error(
            "Error Stripe procesando %s %s: %s",
            tipo,
            event_id,
            type(e).__name__,
        )
        raise HTTPException(
            status_code=500, detail="Error procesando webhook"
        )
    except Exception as e:
        logger.error(
            "Error procesando %s %s: %s",
            tipo,
            event_id,
            type(e).__name__,
        )
        raise HTTPException(
            status_code=500, detail="Error procesando webhook"
        )
    return {"status": "ok"}
