from fastapi.testclient import TestClient

from backend.main import app

cliente = TestClient(app)


def test_me_sin_cookie_devuelve_401():
    respuesta = cliente.get("/api/auth/me")
    assert respuesta.status_code == 401
    assert respuesta.json() == {"error": "No autenticado"}


def test_tickets_sin_cookie_devuelve_401():
    respuesta = cliente.post("/api/tickets", json={"n": 3})
    assert respuesta.status_code == 401
    assert respuesta.json() == {"error": "No autenticado"}


def test_wheel_sin_cookie_devuelve_401():
    respuesta = cliente.post("/api/wheel", json={"core": list(range(1, 11))})
    assert respuesta.status_code == 401
    assert respuesta.json() == {"error": "No autenticado"}


def test_ev_sin_cookie_devuelve_401():
    respuesta = cliente.post(
        "/api/ev",
        json={"bolsa": 60000000, "precio": 15, "ganadores": 2, "tickets": 5},
    )
    assert respuesta.status_code == 401
    assert respuesta.json() == {"error": "No autenticado"}


def test_historico_sin_cookie_devuelve_401():
    respuesta = cliente.get("/api/historico")
    assert respuesta.status_code == 401
    assert respuesta.json() == {"error": "No autenticado"}


def test_health_sin_cookie_devuelve_200():
    respuesta = cliente.get("/api/health")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "ok"}


def test_reglas_default_sin_cookie_devuelve_200():
    respuesta = cliente.get("/api/reglas/default")
    assert respuesta.status_code == 200
