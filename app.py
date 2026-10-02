import os
import random
import streamlit as st

import melate_logic as M

st.set_page_config(
    page_title="Melate Táctico",
    page_icon="🎯",
    layout="centered",
    initial_sidebar_state="collapsed",
)

CSS = """
<style>
:root{
  --az:#1f3a5f; --vd:#2e7d5b; --or:#c9a227; --rj:#c0392b;
}
html, body, [data-testid="stAppViewContainer"]{
  font-size:17px;
}
.block-container{padding-top:1rem;padding-bottom:2rem;max-width:520px !important;}
h1,h2,h3{color:var(--az) !important;}
.stButton button{
  font-size:18px;font-weight:700;padding:.7rem .9rem;border-radius:12px;
  min-height:52px;width:100%;
}
.stDownloadButton button{
  font-size:16px;font-weight:600;padding:.6rem .8rem;border-radius:10px;
  min-height:48px;width:100%;
}
.stButton button[kind="primary"]{background:#2e7d5b;border-color:#2e7d5b;}
div[data-testid="stRadio"] label{font-size:16px;}
.stMetric{background:#f4f6f9;border-radius:10px;padding:8px 12px 6px;}
[data-testid="stExpander"] summary{font-size:16px;font-weight:600;}
pre code{font-size:18px !important;letter-spacing:1px;font-weight:700;}
.regla-ok{color:var(--vd);}
.regla-fail{color:var(--rj);}
.hero{border-left:5px solid var(--or);background:#fff8e7;padding:10px 14px;border-radius:8px;font-size:13.5px;color:#6b5b1c;}
.big-num{font-size:20px;font-weight:800;color:var(--az);}
.chip{display:inline-block;background:#e8f0f8;color:var(--az);border-radius:14px;padding:3px 10px;margin:2px;font-size:13px;}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

st.title("Melate Táctico")
st.caption("Asistente de selección con criterios estadísticos · 6/56 · Lotería Nacional (México)")
st.markdown(
    "<div class='hero'><b>Honestidad primero:</b> ninguna regla, número o algoritmo cambia tu "
    "probabilidad de acertar (el 1er premio siempre es 1 en 32,468,436). Aquí elegimos boletos "
    "<b>impopulares</b> y con <b>valor esperado</b> — para que, si la suerte llega, te toque una parte "
    "mayor y repartas con menos gente.</div>",
    unsafe_allow_html=True,
)

PATH_DATA = os.path.join(os.path.dirname(__file__), "data", "melate_historico.csv")


@st.cache_data(show_spinner=False)
def historico():
    return M.carga_historico(PATH_DATA)


tab_gen, tab_doc, tab_botes = st.tabs(["🎲 Generador", "📘 Estrategia", "💰 Botes / EV"])

with tab_gen:
    st.subheader("Genera tu boleto")
    modo = st.radio(
        "Modo de juego",
        ["Boleto único", "Grupo (N boletos)", "Wheel con cobertura"],
        horizontal=True,
        label_visibility="collapsed",
    )

    with st.expander("🎚️ Reglas anti-populares (cómo elige la máquina)", expanded=True):
        min_altos = st.slider("Números altos (≥32) mínimos — evita fechas de cumpleaños", 0, 6, 3)
        c1 = st.checkbox("Prohibir números consecutivos (p. ej. 7-8)", value=True)
        c2 = st.checkbox("Prohibir mismo último dígito en dos bolas (p. ej. 14 y 24)", value=True)
        c3 = st.checkbox("Exigir al menos 4 décadas distintas (1-10…51-56)", value=True)
        c4 = st.checkbox("Evitar secuencias aritméticas (p. ej. 5-15-25…)", value=True)
        c5 = st.checkbox("Repartir entre las 3 columnas del volante (1-19, 20-39, 40-56)", value=True)
    rules = {
        "min_altos": min_altos,
        "no_consecutivos": c1,
        "no_digitos_repetidos": c2,
        "min_decanas": 4 if c3 else 0,
        "no_secuencias_aritmeticas": c4,
        "columnas": c5,
    }

    if modo == "Boleto único":
        n_boletos = 1
        if st.button("🎲 Generar 1 boleto", type="primary", use_container_width=True):
            rng = random.Random()
            st.session_state["tickets"] = M.generate_group(n_boletos, rng, rules)
    elif modo == "Grupo (N boletos)":
        n_boletos = st.number_input("¿Cuántos boletos?", 1, 12, 5, step=1)
        if st.button("🎲 Generar %d boletos" % n_boletos, type="primary", use_container_width=True):
            rng = random.Random()
            st.session_state["tickets"] = M.generate_group(n_boletos, rng, rules)
    else:
        n_core = st.slider("Tamaño del núcleo (8–14 números)", 8, 14, 10)
        manual = st.toggle("Elegir núcleo manualmente", value=False)
        if manual:
            sel = st.multiselect("Elige los números de tu núcleo", list(range(1, 57)), default=sorted(random.sample(range(1, 57), n_core)))
            core = sorted(sel)[:n_core]
            if len(core) < 6:
                st.warning("Se necesitan al menos 6 números en el núcleo.")
        else:
            core = sorted(random.sample(range(1, 57), n_core))
            st.info("Núcleo automático: " + ", ".join("%02d" % x for x in core))
        if st.button("🛞 Generar wheel con cobertura", type="primary", use_container_width=True):
            if manual and len(core) < 6:
                st.error("Núcleo insuficiente.")
            else:
                tickets = M.greedy_wheel(core)
                tickets = [tuple(sorted(t)) for t in tickets]
                st.session_state["tickets"] = tickets
                st.session_state["wheel_guarantee"] = M.verify_cover(tickets, core)
                st.session_state["wheel_core"] = core

    if "tickets" in st.session_state:
        tickets = st.session_state["tickets"]
        st.divider()
        st.write("**Tus boletos (cada línea = 6 números naturales)**")
        texto = "\n".join(" ".join("%02d" % x for x in t) for t in tickets)
        st.code("\n".join("%02d  %02d  %02d  %02d  %02d  %02d" % t for t in tickets), language=None)
        costo = 15 * len(tickets)
        st.caption(f"Total: {len(tickets)} boletos × $15 = **${costo:,.0f}** MXN por sorteo.")
        st.download_button(
            "⬇️ Descargar .txt para compartir (WhatsApp)",
            data=texto + "\n",
            file_name="melate_tactico.txt",
            mime="text/plain",
            use_container_width=True,
        )
        if "wheel_guarantee" in st.session_state and st.session_state["wheel_guarantee"]:
            core = st.session_state["wheel_core"]
            st.success("✔ Garantía de cobertura verificada: si salen **≥4 numeritos de tu núcleo** ("
                       + ", ".join("%02d" % x for x in core) + "), al menos un boleto tendrá **4 aciertos**.")
        muestra = tickets[0]
        reglas = M.reglas_cumplidas(muestra, rules)
        st.write("**Boleto de ejemplo — reglas aplicadas:**")
        for k, v in reglas.items():
            st.markdown(("✅ " if v else "❌ ") + k)

with tab_doc:
    st.subheader("Cómo se eligen estos boletos (sin magia)")

    st.markdown("""
### El sorteo
Se extraen **7 esferas** del 1 al 56: las primeras 6 son los **números naturales** y la séptima el
**adicional**. Tú eliges **6 números**. Ganas desde acertar 2 números naturales.

| Categoría | Aciertos | Premio |
|---|---|---|
| 1º | 6 naturales | Variable (bolsa) |
| 2º | 5 + adicional | Variable |
| 3º | 5 | Variable |
| 4º | 4 + adicional | Variable |
| 5º | 4 | Variable |
| 6º | 3 + adicional | $161.29 |
| 7º | 3 | $43.01 |
| 8º | 2 + adicional | $32.25 |
| 9º | 2 | $26.88 |

Costo: **$15** por combinación (o $25 con Revancha y $30 con Rosa/Revanchita). Sorteos **miércoles,
viernes y domingo** 21:00. Bolsa mínima garantizada **$30 M**.
""")

    st.markdown("### Probabilidades reales (hipergeométricas, exactas)")
    st.markdown(
        "| Aciertos | Chance |\n|---|---|\n"
        + "| 6 | 1 en 32,468,436 |\n"
        + "| 5 + adicional | 1 en 5,411,406 |\n"
        + "| 5 | 1 en 110,437 |\n"
        + "| 4 + adicional | 1 en 44,175 |\n"
        + "| 4 | 1 en 1,841 |\n"
        + "| 3 + adicional | 1 en 1,380 |\n"
        + "| 3 | 1 en 88 |\n"
        + "| 2 + adicional | 1 en 117 |\n"
        + "| 2 | 1 en 10 |\n"
    )

    st.markdown("""
### Las 4 palancas que usa la app
**1. Boleto anti-popular (reduce repartos).** La gente juega fechas (1-31), secuencias, y patrones
"bonitos". Si esos ganan, se reparten con miles. Un boleto con números ≥32, sin consecutivos, sin
mismo último dígito y sin secuencias tiene exactamente la misma probabilidad, pero los premios se
reparten significativamente menos.

**2. Timing con botes récord.** La bolsa acumula cuando nadie gana el 1º. Jugar cuando el bote es
históricamente alto mejora el valor esperado. La pestaña **Botes / EV** te dice si hoy es un buen día.

**3. Wheels de cobertura.** Si eliges un núcleo de 8–14 números, un wheel genera boletos garantizados:
si salen ≥4 de tu núcleo, al menos un boleto acerta 4. No cambia el azar, cambia la *cobertura*.

**4. Diversificación de núcleos.** Al jugar varios boletos, cada uno usa números distintos y zonas
distintas: nunca duplicas el mismo riesgo con variaciones del mismo patrón.

### Lo que NO funciona (y por qué)
- **Números fríos/calientes:** un sorteo justo no tiene memoria.
- **Paridad, suma "cercana a la media":** placebo; no cambia la probabilidad de acertar.
- **Machine learning / deep learning:** imposible predecir bolas con información perfecta y uniforme.

> **Juego responsable.** Melate es una lotería con esperanza matemática negativa a largo plazo.
> Juega solo por diversión y con dinero que puedas perder. Si sientes que pierdes el control, llama a
> Conadic (800 911 2000, México). +18 años.
""")

with tab_botes:
    st.subheader("¿Es buen momento para jugar?")
    h = historico()
    if len(h):
        ultimo = int(h["BOLSA"].iloc[-1])
        ult_fecha = h["FECHA"].iloc[-1].strftime("%d/%m/%Y")
        streak = M.streak_actual(h)
        alto = M.es_periodo_bote_alto(h)
        st.metric("Último bote registrado", "$%s M" % f"{ultimo/1e6:,.0f}", ult_fecha)
        st.metric("Sorteos acumulando en racha", "≈ %d" % (streak + 1))
        if alto:
            st.success("🗺️ Bote históricamente alto y en racha: estadísticamente es de los **mejores momentos** para jugar con criterio de EV.")
        else:
            st.info("El bote actual aún no está en zona récord. Puedes esperar a que acumule.")

        st.caption("Serie histórica de la bolsa (era 6/56, concurso 2089+)")
        st.line_chart(h.set_index("CONCURSO")["BOLSA"] / 1e6, height=200)

    st.divider()
    st.subheader("Calculadora de valor esperado (EV)")
    ultimo = int(h["BOLSA"].iloc[-1]) if len(h) else 60000000
    c1, c2 = st.columns(2)
    with c1:
        bote = st.number_input("Bote acumulado (MXN)", value=ultimo, step=1000000, min_value=0)
        precio = st.number_input("Precio por boleto (MXN)", value=15, step=5, min_value=1)
    with c2:
        ganadores = st.slider("Ganadores esperados del 1er lugar", 1, 10, 2)
        n_tickets = st.number_input("Boletos a comprar", 1, 20, 5, step=1)

    r = M.ev_calculator(bote, precio, ganadores, n_tickets)
    m1, m2, m3 = st.columns(3)
    m1.metric("EV por boleto", "$%.2f" % r["ev_boleto"])
    m2.metric("Costo total", "$%d" % (precio * n_tickets))
    m3.metric("P(ganar algo)", "1 en %.1f" % (1 / r["prob_ganar_algo"]))

    st.markdown(f"""
- **EV por boleto:** ${r['ev_boleto']:.2f} (precio ${precio:,.0f}). Incluye el 1er lugar **repartido
  entre {ganadores}** y los premios fijos (6º–9º). Las categorías 2º–5º (variables) no se estiman aquí.
- **Punto de equilibrio (break-even del bote):** ≈ **${r['break_even']/1e6:,.0f} M** de pesos.
  Si el bote supera esa cifra, el EV del boleto rebasa su costo (antes de impuestos y sin considerar
  que más jugadores entran con botes grandes).
- **EV de la sesión** para {n_tickets} boletos: **${r['ev_sesion']:,.2f}**.
""")
    if r["ev_boleto"] >= precio:
        st.warning("EV alto: el boleto tiene esperanza positiva *en teoría*. Recuerda que con botes "
                   "récord más gente juega y el reparto crece: suele ser la **única** ventana donde el "
                   "juego deja de ser perdedor esperado.")
    else:
        st.caption("Con botes normales, el boleto tiene esperanza negativa (costo ≥ EV). Es la norma "
                   "de cualquier lotería: se juega por el entretenimiento, no como inversión.")

st.markdown("---")
st.caption("Hecho con datos públicos del sorteo Melate · Análisis estadístico sobre 4,268 sorteos · "
           "No afiliado a Lotería Nacional · +18")