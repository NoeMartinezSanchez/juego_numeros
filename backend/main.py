import random
from functools import lru_cache
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

import melate_logic as M
from backend.auth import SESSION_SECRET, router as auth_router, usuario_actual
from backend.schemas import (
    EstadisticasBolsa,
    EvRequest,
    HealthResponse,
    HistoricoResponse,
    RangoFechas,
    ReglaEstado,
    TicketsRequest,
    TicketsResponse,
    UltimoSorteo,
    WheelRequest,
    WheelResponse,
)

PATH_DATA = Path(__file__).resolve().parent.parent / "data" / "melate_historico.csv"

app = FastAPI(title="Melate Táctico API")

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/auth")


@lru_cache(maxsize=1)
def _historico():
    return M.carga_historico(str(PATH_DATA))


def _validar_reglas(rules):
    if rules is None:
        return {}
    if not isinstance(rules, dict):
        raise HTTPException(status_code=400, detail="El campo rules debe ser un objeto.")
    permitidas = set(M.DEFAULT_RULES)
    for clave, valor in rules.items():
        if clave not in permitidas:
            raise HTTPException(status_code=400, detail="Regla desconocida: %s." % clave)
        if clave in ("min_altos", "min_decanas"):
            if isinstance(valor, bool) or not isinstance(valor, int) or not 0 <= valor <= 6:
                raise HTTPException(
                    status_code=400,
                    detail="La regla %s debe ser un entero entre 0 y 6." % clave,
                )
        elif not isinstance(valor, bool):
            raise HTTPException(
                status_code=400, detail="La regla %s debe ser booleana." % clave
            )
    return rules


@app.exception_handler(RequestValidationError)
async def _error_validacion(request: Request, exc: RequestValidationError):
    campos = []
    for error in exc.errors():
        partes = [str(p) for p in error.get("loc", []) if p != "body"]
        if partes:
            campos.append(".".join(partes))
    detalle = ", ".join(dict.fromkeys(campos))
    mensaje = "Entrada inválida."
    if detalle:
        mensaje = "Entrada inválida. Revisa: %s." % detalle
    return JSONResponse(status_code=400, content={"error": mensaje})


@app.exception_handler(StarletteHTTPException)
async def _error_http(request: Request, exc: StarletteHTTPException):
    mensaje = exc.detail
    if exc.status_code == 404 and mensaje == "Not Found":
        mensaje = "Recurso no encontrado."
    return JSONResponse(status_code=exc.status_code, content={"error": mensaje})


@app.exception_handler(Exception)
async def _error_interno(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500, content={"error": "Error interno del servidor."}
    )


@app.get("/api/health", response_model=HealthResponse)
def health():
    return {"status": "ok"}


@app.get("/api/reglas/default")
def reglas_default():
    return M.DEFAULT_RULES


@app.post("/api/tickets", response_model=TicketsResponse)
def crear_tickets(payload: TicketsRequest, _usuario=Depends(usuario_actual)):
    reglas_extra = _validar_reglas(payload.rules)
    rules_efectivas = dict(M.DEFAULT_RULES, **reglas_extra)
    if payload.seed is None:
        rng = random.Random()
    else:
        rng = random.Random(payload.seed)
    tickets = M.generate_group(payload.n, rng, rules_efectivas, max_overlap=2)
    tickets = [tuple(sorted(t)) for t in tickets]
    detalle = [
        [
            ReglaEstado(label=label, cumple=bool(cumple))
            for label, cumple in M.reglas_cumplidas(t, rules_efectivas).items()
        ]
        for t in tickets
    ]
    return TicketsResponse(tickets=[list(t) for t in tickets], reglas=detalle)


@app.get("/api/historico", response_model=HistoricoResponse)
def obtener_historico(_usuario=Depends(usuario_actual)):
    df = _historico()
    if len(df) == 0:
        return HistoricoResponse(
            total_sorteos=0,
            rango_fechas=RangoFechas(desde="", hasta=""),
            ultimos_sorteos=[],
            streak_actual=0,
            periodo_bote_alto=False,
            estadisticas_bolsa=EstadisticasBolsa(
                min=0.0, max=0.0, media=0.0, mediana=0.0
            ),
        )
    fechas = df["FECHA"]
    bolsa = df["BOLSA"]
    ultimos = [
        UltimoSorteo(
            concurso=int(fila["CONCURSO"]),
            fecha=fila["FECHA"].date().isoformat(),
            bolsa=float(fila["BOLSA"]),
        )
        for _, fila in df.tail(10).iterrows()
    ]
    return HistoricoResponse(
        total_sorteos=int(len(df)),
        rango_fechas=RangoFechas(
            desde=fechas.min().date().isoformat(),
            hasta=fechas.max().date().isoformat(),
        ),
        ultimos_sorteos=ultimos,
        streak_actual=int(M.streak_actual(df)),
        periodo_bote_alto=bool(M.es_periodo_bote_alto(df)),
        estadisticas_bolsa=EstadisticasBolsa(
            min=float(bolsa.min()),
            max=float(bolsa.max()),
            media=float(bolsa.mean()),
            mediana=float(bolsa.median()),
        ),
    )


@app.post("/api/wheel", response_model=WheelResponse)
def crear_wheel(payload: WheelRequest, _usuario=Depends(usuario_actual)):
    core = payload.core
    if len(core) < 7 or len(core) > 20:
        raise HTTPException(
            status_code=400,
            detail="El núcleo debe tener entre 7 y 20 números.",
        )
    if any(n < 1 or n > 56 for n in core):
        raise HTTPException(
            status_code=400,
            detail="Los números del núcleo deben estar entre 1 y 56.",
        )
    if len(set(core)) != len(core):
        raise HTTPException(
            status_code=400,
            detail="Los números del núcleo deben ser distintos.",
        )
    tickets = M.greedy_wheel(core)
    tickets = [tuple(sorted(t)) for t in tickets]
    garantia = bool(M.verify_cover(tickets, core))
    return WheelResponse(tickets=[list(t) for t in tickets], garantia=garantia)


@app.post("/api/ev")
def calcular_ev(payload: EvRequest, _usuario=Depends(usuario_actual)):
    return M.ev_calculator(
        payload.bolsa, payload.precio, payload.ganadores, payload.tickets
    )
