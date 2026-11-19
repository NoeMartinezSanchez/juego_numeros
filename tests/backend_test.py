from fastapi.testclient import TestClient
import pytest

import melate_logic as M
from backend.auth import usuario_actual
from backend.billing import acceso_generacion, suscripcion_activa
from backend.main import app

cliente = TestClient(app)


@pytest.fixture(autouse=True)
def autenticar():
    app.dependency_overrides[usuario_actual] = lambda: {
        "id": 1,
        "email": "test@example.com",
    }
    app.dependency_overrides[suscripcion_activa] = lambda: {
        "user_id": 1,
        "status": "active",
        "current_period_end": "2100-01-01T00:00:00+00:00",
    }
    app.dependency_overrides[acceso_generacion] = lambda: {
        "tipo": "suscripcion",
        "usuario": {"id": 1, "email": "test@example.com"},
        "creditos": None,
    }
    yield
    app.dependency_overrides.pop(usuario_actual, None)
    app.dependency_overrides.pop(suscripcion_activa, None)
    app.dependency_overrides.pop(acceso_generacion, None)


def test_health():
    respuesta = cliente.get("/api/health")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "ok"}


def test_reglas_default():
    respuesta = cliente.get("/api/reglas/default")
    assert respuesta.status_code == 200
    assert set(M.DEFAULT_RULES).issubset(respuesta.json().keys())


def test_tickets_estructura_alineada():
    respuesta = cliente.post("/api/tickets", json={"n": 3})
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert len(datos["tickets"]) == 3
    assert len(datos["reglas"]) == 3
    for ticket, reglas in zip(datos["tickets"], datos["reglas"]):
        assert isinstance(reglas, list)
        assert len(reglas) == 5
        esperadas = list(M.reglas_cumplidas(tuple(ticket), M.DEFAULT_RULES).items())
        obtenidas = [(regla["label"], regla["cumple"]) for regla in reglas]
        assert obtenidas == esperadas
        for regla in reglas:
            assert isinstance(regla["label"], str)
            assert isinstance(regla["cumple"], bool)


def test_tickets_n_fuera_de_rango():
    for n in (0, 51):
        respuesta = cliente.post("/api/tickets", json={"n": n})
        assert respuesta.status_code == 400
        assert "error" in respuesta.json()


def test_tickets_seed_determinista():
    primera = cliente.post("/api/tickets", json={"n": 2, "seed": 42})
    segunda = cliente.post("/api/tickets", json={"n": 2, "seed": 42})
    assert primera.status_code == 200
    assert segunda.status_code == 200
    assert primera.json()["tickets"] == segunda.json()["tickets"]


def test_historico_claves():
    respuesta = cliente.get("/api/historico")
    assert respuesta.status_code == 200
    datos = respuesta.json()
    claves = (
        "total_sorteos",
        "rango_fechas",
        "ultimos_sorteos",
        "streak_actual",
        "periodo_bote_alto",
        "estadisticas_bolsa",
    )
    for clave in claves:
        assert clave in datos


def test_wheel_valido():
    core = list(range(1, 11))
    respuesta = cliente.post("/api/wheel", json={"core": core})
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["garantia"] is True
    for ticket in datos["tickets"]:
        assert isinstance(ticket, list)
        assert len(ticket) == 6
        assert ticket == sorted(ticket)
        assert len(set(ticket)) == 6
        assert all(1 <= n <= 56 for n in ticket)


def test_wheel_invalido():
    cores = (
        [1, 2, 3, 4, 5, 6],
        [1, 2, 3, 4, 5, 6, 57],
        [1, 1, 2, 3, 4, 5, 6],
    )
    for core in cores:
        respuesta = cliente.post("/api/wheel", json={"core": core})
        assert respuesta.status_code == 400
        assert "error" in respuesta.json()


def test_ev_claves():
    respuesta = cliente.post(
        "/api/ev",
        json={"bolsa": 60000000, "precio": 15, "ganadores": 2, "tickets": 5},
    )
    assert respuesta.status_code == 200
    datos = respuesta.json()
    for clave in ("ev_boleto", "ev_sesion", "prob_ganar_algo", "break_even"):
        assert clave in datos
