import random
import pandas as pd
import numpy as np
from math import comb


def rng_for(seed=None):
    return random.Random(seed)


DEFAULT_RULES = {
    "min_altos": 3,
    "no_consecutivos": True,
    "no_digitos_repetidos": True,
    "min_decanas": 4,
    "no_secuencias_aritmeticas": True,
    "columnas": True,
}

_COLUMNAS = [(1, 19), (20, 39), (40, 56)]


def _decana(n):
    return (n - 1) // 10


def _columna(n):
    for c, (lo, hi) in enumerate(_COLUMNAS):
        if lo <= n <= hi:
            return c
    return 2


def _es_consecutivo(t):
    for i in range(len(t) - 1):
        if t[i + 1] - t[i] == 1:
            return False
    return True


def _es_secuencia_aritmetica(t):
    if len(t) < 3:
        return True
    for d in range(1, 20):
        if set(t) == set(range(t[0], t[-1] + 1, d)):
            return True
    return False


def reglas_cumplidas(t, rules):
    t = tuple(sorted(t))
    out = {}
    if rules.get("no_consecutivos"):
        out["No consecutivos"] = _es_consecutivo(t)
    if rules.get("no_digitos_repetidos"):
        dig = [x % 10 for x in t]
        out["Último dígito distinto"] = len(set(dig)) == len(dig)
    if rules.get("min_decanas"):
        out["≥%d décadas distintas" % rules["min_decanas"]] = len({_decana(x) for x in t}) >= rules["min_decanas"]
    if rules.get("no_secuencias_aritmeticas"):
        out["Sin secuencia aritmética"] = not _es_secuencia_aritmetica(t)
    if rules.get("columnas"):
        out["Cubre ≥2 columnas"] = len({_columna(x) for x in t}) >= 2
    return out


def generate_ticket(rng, rules, forced_altos=None):
    rules = dict(DEFAULT_RULES, **rules)
    min_altos = rules.get("min_altos") or 0
    for _ in range(400):
        pool = list(range(1, 57))
        t = set()
        if min_altos and forced_altos is None:
            altos = rng.sample(range(32, 57), min(min_altos, 25))
            t = set(altos)
        while len(t) < 6:
            t.add(rng.choice(pool))
        tick = tuple(sorted(t))
        if len(tick) != 6:
            continue
        ok = True
        if rules.get("no_consecutivos") and not _es_consecutivo(tick):
            ok = False
        if ok and rules.get("no_digitos_repetidos") and len({x % 10 for x in tick}) != 6:
            ok = False
        if ok and rules.get("min_decanas") and len({_decana(x) for x in tick}) < rules["min_decanas"]:
            ok = False
        if ok and rules.get("no_secuencias_aritmeticas") and _es_secuencia_aritmetica(tick):
            ok = False
        if ok and rules.get("columnas") and len({_columna(x) for x in tick}) < 2:
            ok = False
        if ok:
            return tick
    return tuple(sorted(rng.sample(range(1, 57), 6)))


def generate_group(n, rng, rules, max_overlap=2):
    results = []
    attempts = 0
    while len(results) < n and attempts < n * 400:
        tick = generate_ticket(rng, rules)
        attempts += 1
        if len(results) >= n:
            break
        overlap = max((len(set(tick) & set(prev)) for prev in results), default=0)
        if overlap <= max_overlap:
            results.append(tick)
    while len(results) < n:
        results.append(generate_ticket(rng, rules))
    return results


def greedy_wheel(core_nums, k=6, t=4):
    import itertools
    core = sorted(core_nums)
    fours = list(itertools.combinations(core, t))
    all6 = list(itertools.combinations(core, k))
    four_set = [set(f) for f in fours]
    cover = []
    for s in all6:
        ss = set(s)
        idx = [i for i, f in enumerate(four_set) if f.issubset(ss)]
        cover.append(set(idx))
    uncovered = set(range(len(fours)))
    chosen = []
    while uncovered:
        best = -1
        best_cnt = -1
        for i, c in enumerate(cover):
            if i in chosen:
                continue
            cnt = len(c & uncovered)
            if cnt > best_cnt:
                best_cnt, best = cnt, i
        chosen.append(best)
        uncovered -= cover[best]
    return [tuple(sorted(all6[i])) for i in chosen]


def verify_cover(tickets, core, t=4):
    import itertools
    core = sorted(core)
    fours = list(itertools.combinations(core, t))
    for f in fours:
        if not any(set(f).issubset(set(tk)) for tk in tickets):
            return False
    return True


def ev_calculator(bolsa, precio=15, ganadores=1, tickets=1):
    C = comb(56, 6)
    p6 = 1.0 / C
    p5ad = 6.0 / C
    p5 = 6 * 49.0 / C
    p4ad = 15 * 49.0 / C
    p4 = 15 * comb(49, 2) / C
    p3ad = 20 * comb(49, 2) / C
    p3 = 20 * comb(49, 3) / C
    p2ad = 15 * comb(49, 3) / C
    p2 = 15 * comb(49, 4) / C
    premios_fijos = {
        "6° (3+adicional)": (p3ad, 161.29),
        "7° (3)": (p3, 43.01),
        "8° (2+adicional)": (p2ad, 32.25),
        "9° (2)": (p2, 26.88),
    }
    ev_fijo = sum(p * m for p, m in premios_fijos.values())
    ev_1er = p6 * bolsa / max(ganadores, 1)
    ev_total_boleto = ev_1er + ev_fijo
    costo_total = precio * tickets
    ev_sesion = ev_total_boleto * tickets - costo_total
    prob_ganar_algo = p2 + p2ad + p3 + p3ad + p4 + p4ad + p5 + p5ad + p6
    return {
        "C": C,
        "p6": p6,
        "p5ad": p5ad,
        "p5": p5,
        "p4ad": p4ad,
        "p4": p4,
        "p3ad": p3ad,
        "p3": p3,
        "p2ad": p2ad,
        "p2": p2,
        "ev_fijo": ev_fijo,
        "ev_1er": ev_1er,
        "ev_boleto": ev_total_boleto,
        "ev_sesion": ev_sesion,
        "prob_ganar_algo": prob_ganar_algo,
        "bolsa": bolsa,
        "precio": precio,
        "ganadores": ganadores,
        "tickets": tickets,
        "break_even": (precio - ev_fijo) * C * ganadores if ev_fijo < precio else 0,
    }


def carga_historico(path="data/melate_historico.csv"):
    df = pd.read_csv(path, parse_dates=["FECHA"], dayfirst=True)
    df = df.sort_values("CONCURSO").reset_index(drop=True)
    return df


def streak_actual(df):
    s = df["BOLSA"].to_numpy()
    n = len(s)
    k = 0
    for i in range(n - 1, 0, -1):
        if s[i - 1] > 0 and s[i] >= s[i - 1]:
            k += 1
        else:
            break
    return k


def es_periodo_bote_alto(df, fractil=0.9):
    s = df["BOLSA"].to_numpy()
    if len(s) == 0:
        return False
    umbral = np.percentile(s[s > 0], fractil * 100)
    return s[-1] >= umbral and streak_actual(df) >= 5