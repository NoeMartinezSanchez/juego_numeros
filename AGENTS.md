# AGENTS.md — Melate Táctico

App (Spanish UI) that generates Melate 6/56 lottery ticket suggestions using
statistical criteria (anti-popular combos, coverage wheels, expected value).
Pure logic lives in `melate_logic.py`. The UI is migrating from Streamlit
(`app.py`, legacy) to a FastAPI backend (`backend/`) plus a vanilla HTML/JS
frontend (`frontend/`).

Repo root is this directory (`melate-app/`). Run every command from here.

> Ethical constraint: this is an educational tool. Never phrase anything as
> "predicting"/"beating" the draw, and keep the honest disclaimer prominent.

---

## 1. Build / run / verify commands

No build step, no bundler, no compiled artifacts. Streamlit runs the app directly.

### Install dependencies
```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
```

### Run the app (dev)
```bash
streamlit run app.py
# optional, to test from phone on the same LAN:
streamlit run app.py --server.address 0.0.0.0
```
Opens at `http://localhost:8501` by default.

### Sanity-check the logic engine (fast, no web UI)
The repo has no formal test suite yet. Run these inline checks instead:
```bash
# Reglas por defecto se respetan + resumen de reglas
python -c "import random, melate_logic as M; rng=random.Random(1); print([M.reglas_cumplidas(M.generate_ticket(rng, M.DEFAULT_RULES), M.DEFAULT_RULES) for _ in range(3)])"

# Wheel: núcleo 10 -> boletos y garantía de cobertura
python -c "import random, melate_logic as M; c=sorted(random.sample(range(1,57),10)); t=M.greedy_wheel(c); print(len(t), M.verify_cover(t,c))"

# EV: valores numéricos coherentes
python -c "import melate_logic as M; r=M.ev_calculator(60000000,15,2,5); print(round(r['ev_boleto'],2), round(r['ev_sesion'],2))"
```

### Running a single test
If you add tests, use pytest and the standard selectors:
```bash
pip install pytest
python -m pytest tests/melate_logic_test.py                    # one file
python -m pytest tests/melate_logic_test.py::test_x -v        # one test
python -m pytest -q                                           # whole suite
```
Keep tests under `tests/`, filename `<module>_test.py`. Prioritize cheap
invariants: (1) generated tickets respect the rules toggled in
`reglas_cumplidas`; (2) group overlap `<= max_overlap`; (3) `greedy_wheel`
always satisfies `verify_cover`; (4) EV consistency
(`p2+..+p6 == prob_ganar_algo`, break-even bote makes `ev_boleto >= precio`);
(5) `streak_actual` on the bundled CSV.

### Lint / typecheck
Not configured. No `pyproject.toml`/`setup.cfg` lint or type tooling exists.
If you add tooling, prefer `ruff` (lint) — keep it permissive so the current
single-file style keeps passing. Do not add mypy as a CI gate: the codebase
currently has no type annotations by convention.

---

## 2. Arquitectura FastAPI (migración en curso)

- **`backend/main.py`** — FastAPI app. Expone `/api/health`,
  `/api/reglas/default`, `/api/tickets`, `/api/historico`, `/api/wheel`, `/api/ev`.
  CORS habilitado solo para `http://localhost:5173` y `http://localhost:8000`.
  Entradas inválidas responden `400` con `{"error": "mensaje"}` en español;
  ninguna excepción debe tumbar el servidor.
- **`backend/schemas.py`** — modelos Pydantic de request/response. Los tickets
  se serializan como listas de ints; internamente siguen siendo `tuple` ordenada.
- **`frontend/`** — `index.html`, `app.js`, `styles.css`. HTML/JS vanilla, sin
  React ni bundler. Mobile-first, `max-width:520px`, botones `min-height:52px`.
  Consume la API con `fetch` contra `http://localhost:8000`.
- **`melate_logic.py`** — sin cambios en esta migración. Toda la semántica de
  generación, reglas, wheel y EV sale de aquí.
- **`data/melate_historico.csv`** — sin cambios. Solo lo lee
  `carga_historico()`; las agregaciones de BOLSA (min/max/media/mediana) viven
  en `backend/main.py` con pandas.
- **`app.py`** — legado Streamlit. Sigue existiendo hasta que se retire; no
  agregar features nuevas ahí.

Endpoints y fuente lógica:

| Endpoint | Función de `melate_logic.py` |
|---|---|
| `GET /api/health` | — |
| `GET /api/reglas/default` | `DEFAULT_RULES` |
| `POST /api/tickets` | `generate_group`, `reglas_cumplidas` |
| `GET /api/historico` | `carga_historico`, `streak_actual`, `es_periodo_bote_alto` |
| `POST /api/wheel` | `greedy_wheel`, `verify_cover` |
| `POST /api/ev` | `ev_calculator` |

`/api/tickets` devuelve `reglas` como lista alineada por ticket
(`reglas[i]` corresponde a `tickets[i]`). `forced_altos` y `max_overlap` no se
exponen. `/api/wheel` acepta núcleos de 7 a 20 números distintos en `1..56`
(nota: tamaños ≥18 pueden tardar decenas de segundos). `seed` solo aplica a
`/api/tickets`; `greedy_wheel` es determinista y no recibe RNG.

### Ejecución local (FastAPI + frontend)
```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt

# terminal 1: backend
uvicorn backend.main:app --reload
# API en http://localhost:8000 (docs en /docs)

# terminal 2: frontend estático
python -m http.server 5173 -d frontend
# UI en http://localhost:5173
```

El frontend estático debe servirse en el puerto `5173` para coincidir con la
lista de orígenes CORS. `app.py` sigue corriendo con `streamlit run app.py`
mientras no se retire.

---

## 3. Architecture (Streamlit legado)

- **`app.py`** — Streamlit entry point. Top-level script executed on every
  rerun (Streamlit model). Owns: `st.set_page_config`, inline CSS, the 3 tabs
  (`tab_gen`, `tab_doc`, `tab_botes`), widget state, and rendering.
- **`melate_logic.py`** — Pure, importable logic. No `streamlit` imports.
  Functions receive an injectable `random.Random` (`rng`) so behavior is
  reproducible for tests.
- **`data/melate_historico.csv`** — Embedded BOLSA history (era 6/56). Read via
  `carga_historico()`; keep it committed (app is deployed offline-friendly).
- **`requirements.txt`** — `streamlit`, `pandas`, `numpy` para el legado, más
  `fastapi` y `uvicorn[standard]` para la API. Evita dependencias pesadas
  (React, Vite, ORM, bases de datos).

Plan rule of thumb: put reusable math in `melate_logic.py` as pure functions;
keep `app.py` for presentation only. If logic needs a new knob the UI exposes,
add it as a parameter in the logic function.

---

## 4. Code style

### Imports
- stdlib first (`os`, `random`), then third-party (`pandas`, `numpy`,
  `streamlit`), then local module: `import melate_logic as M`.
- `melate_logic` is imported as `M` in `app.py` — keep that alias for reads.
- Inside function-local needs, import on demand (e.g. `greedy_wheel` uses
  `import itertools` locally). No other local-import pattern in the codebase.

### Formatting / line length
- ~88 col soft limit, 79 hard. Wrap long string concatenations with implicit
  parens over multiple lines (see `st.markdown` blocks in `app.py`).
- 4 spaces, no tabs; 2 blank lines between top-level defs; functions do one
  logical idea each.
- `%` formatting for most Spanish user strings and `f"..."` for captions mixing
  variables; both appear — do not churn existing strings.

### Naming
- Files/modules/functions: `snake_case`, concise Spanish names
  (`generate_ticket`, `generate_group`, `greedy_wheel`, `carga_historico`,
  `streak_actual`, `es_periodo_bote_alto`, `reglas_cumplidas`).
- Private helpers: single leading underscore (`_decana`, `_columna`,
  `_es_consecutivo`, `_es_secuencia_aritmetica`).
- Module constants: `UPPER_SNAKE` (`DEFAULT_RULES`, `_COLUMNAS`).
- User-facing strings: **Spanish**.

### Types
- No type annotations in the codebase (follow existing convention). Optional
  on new pure functions; do not retrofit the whole codebase.

### Docstrings / comments
- The codebase has **no comments or docstrings** by design. Keep code
  self-explanatory via clear names; do not add explanatory inline comments.

### Data & return shapes (important invariants)
- A "ticket" is a `tuple` of **6 distinct ints**, sorted ascending, in `1..56`
  — always `tuple(sorted(...))`. Never return a list/set from generation.
- `generate_ticket(rng, rules, forced_altos=None)` merges caller rules over
  `DEFAULT_RULES`; on 400 failed attempts it falls back to a plain random
  ticket (graceful, never crash).
- `reglas_cumplidas(t, rules)` returns `dict {Spanish label: bool}` — used by
  the UI to render ✅/❌.
- `ev_calculator` returns a flat dict; keep its keys stable (`ev_boleto`,
  `ev_sesion`, `prob_ganar_algo`, `break_even`, ...).
- Rules dict keys are Spanish snake keys: `min_altos`, `no_consecutivos`,
  `no_digitos_repetidos`, `min_decanas`, `no_secuencias_aritmeticas`,
  `columnas`.

### Error handling
- Graceful degradation over raising: generation falls back to uniform random;
  divisions guard with `max(ganadores, 1)`; empty series return safe values
  (`es_periodo_bote_alto` returns `False`).
- `st.session_state` keys are checked with `in` before reads (`if "tickets" in
  st.session_state`). Wheel mode adds `st.session_state["wheel_guarantee"]` and
  `["wheel_core"]`.
- Never `raise` inside `app.py` rendering paths — Streamlit reruns make that
  crash-prone; use `st.error`/`st.warning` instead.

---

## 5. Streamlit / UI conventions

- `st.set_page_config(layout="centered")` stays. Mobile-first: keep
  `max-width:520px` container CSS as-is; big touch targets (min-height 52px
  buttons). Don't add wide desktop-only layouts that break mobile.
- Data loading: `@st.cache_data(show_spinner=False)` on `historico()`.
- State: generation results live in `st.session_state["tickets"]`; wheel mode
  also sets `wheel_guarantee` and `wheel_core`. Reset/invalidate those keys
  when you change modes.
- New UI must keep the "Honestidad primero" hero box and the +18 responsible
  gambling note (Conadic reference). Emojis in tab names/labels (🎲 📘 💰)
  are the established pattern.

---

## 6. Git workflow

- Default branch `main`; remote
  `https://github.com/NoeMartinezSanchez/juego_numeros.git`.
- Commit in Spanish, imperative summary first line (e.g. `"Melate Táctico:
  generador + estrategia + EV"`); keep commits small per feature/fix.
- Streamlit Cloud redeploys on every `git push` to `main`.
- `__pycache__/`, `.venv/`, `.env`, `.streamlit/secrets.toml`, `*.log` are
  gitignored; keep it complete. Never commit real secrets.