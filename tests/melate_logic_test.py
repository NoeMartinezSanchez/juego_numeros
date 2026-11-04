import itertools
import math
import random

import melate_logic as M


def test_generate_ticket_devuelve_tuple_valida():
    for seed in range(50):
        ticket = M.generate_ticket(random.Random(seed), M.DEFAULT_RULES)
        assert isinstance(ticket, tuple)
        assert len(ticket) == 6
        assert all(isinstance(n, int) for n in ticket)
        assert len(set(ticket)) == 6
        assert ticket == tuple(sorted(ticket))
        assert all(1 <= n <= 56 for n in ticket)


def test_generate_ticket_respeta_reglas_por_defecto():
    for seed in range(50):
        ticket = M.generate_ticket(random.Random(seed), M.DEFAULT_RULES)
        reglas = M.reglas_cumplidas(ticket, M.DEFAULT_RULES)
        assert len(reglas) == 5
        assert all(reglas.values())


def test_generate_ticket_con_reglas_relajadas_devuelve_tuple_valida():
    reglas_relajadas = {clave: False for clave in M.DEFAULT_RULES}
    for seed in range(50):
        ticket = M.generate_ticket(random.Random(seed), reglas_relajadas)
        assert isinstance(ticket, tuple)
        assert len(ticket) == 6
        assert len(set(ticket)) == 6
        assert ticket == tuple(sorted(ticket))
        assert all(1 <= n <= 56 for n in ticket)


def test_generate_group_respeta_solapamiento_maximo():
    tickets = M.generate_group(10, random.Random(1), M.DEFAULT_RULES, max_overlap=2)
    assert len(tickets) == 10
    for primero, segundo in itertools.combinations(tickets, 2):
        assert len(set(primero) & set(segundo)) <= 2


def test_greedy_wheel_cubre_nucleo():
    for tamano in (10, 12):
        core = list(range(1, tamano + 1))
        tickets = M.greedy_wheel(core)
        assert M.verify_cover(tickets, core) is True


def test_ev_calculator_probabilidades_y_break_even():
    resultado = M.ev_calculator(60_000_000, 15, 2, 5)
    suma = (
        resultado["p2"]
        + resultado["p2ad"]
        + resultado["p3"]
        + resultado["p3ad"]
        + resultado["p4"]
        + resultado["p4ad"]
        + resultado["p5"]
        + resultado["p5ad"]
        + resultado["p6"]
    )
    assert abs(suma - resultado["prob_ganar_algo"]) < 1e-12
    assert resultado["ev_fijo"] < resultado["precio"]
    assert resultado["break_even"] > 0
    assert math.isfinite(resultado["ev_boleto"])
    assert math.isfinite(resultado["ev_sesion"])


def test_carga_historico_y_streak_actual():
    df = M.carga_historico()
    assert len(df) > 0
    streak = M.streak_actual(df)
    assert isinstance(streak, int)
    assert streak >= 0
