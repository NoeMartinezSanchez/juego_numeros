# Melate Táctico 🎯

Asistente de selección de boletos Melate (6/56, Lotería Nacional de México) con
criterios estadísticos — móvil primero, listo para **Streamlit Cloud**.

**Honestidad antes que nada:** ninguna herramienta puede predecir el número ganador; en un
sorteo justo cada combinación tiene probabilidad `1/C(56,6)`. Esta app aplica los **criterios
estadísticos legítimos** extraídos del EDA del histórico (4,268 sorteos) para reducir premios
compartidos y mejorar el valor esperado.

## Características

- 🎲 **Generador** con 3 modos:
  - **Boleto único** anti-popular (números ≥32, sin consecutivos, sin último dígito repetido,
    ≥4 décadas, sin secuencias, 3 columnas).
  - **Grupo de N boletos** con diversificación de núcleos (máx. 2 números repetidos entre boletos).
  - **Wheel con cobertura** (núcleo de 8–14 números): garantía verificada de que si salen ≥4
    números de tu núcleo, al menos un boleto tendrá **4 aciertos**.
- 📘 **Pestaña Estrategia** que documenta y explica cómo se eligen los boletos (reglas oficiales,
  probabilidades exactas, las 4 palancas y qué NO funciona).
- 💰 **Botes / EV**: serie histórica del bote (era 6/56), racha de acumulación actual y
  calculadora de valor esperado con parámetro editable de reparto (ganadores esperados).
- 📱 **Móvil primero** y descarga `.txt` para compartir por WhatsApp.

## Duración de la racha de acumulación

La app usa el histórico embebido en `data/melate_historico.csv` (concursos 2089+, era 6/56)
para calcular cuántos sorteos lleva el bote acumulándose y determinar si está en "zona récord".

## Probabilidades de referencia (6/56)

| Premio | Probabilidad |
|---|---|
| 1er (6 bolas) | 1 en 32,468,436 |
| 2° (5 + adicional) | 1 en 5,411,406 |
| 3° (5) | 1 en 110,437 |
| 4° (4 + adicional) | 1 en 44,175 |
| 5° (4) | 1 en 1,841 |
| 6° (3 + adicional) | 1 en 1,380 |
| 7° (3) | 1 en 88 |
| 8° (2 + adicional) | 1 en 117 |
| 9° (2) | 1 en 10 |

Costo oficial por combinación: **$15 MXN** (o $25 con Revancha, $30 con Revancha + Revanchita).
Sorteos: miércoles, viernes y domingo, 21:00 h.

## Ejecución local

Requiere Python 3.9+.

```bash
cd melate-app
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
streamlit run app.py
```

Abre `http://localhost:8501` en tu navegador (también desde tu teléfono si estás en la misma red,
remplazando `localhost` por la IP de tu equipo, p. ej. `http://192.168.1.10:8501`).

## Publicar en GitHub

1. Crea un repositorio vacío en GitHub (sin README) llamado, p. ej. `melate-tactico`.
2. Desde la carpeta del proyecto:

```bash
cd melate-app
git init
git add .
git commit -m "Melate Táctico: generador + estrategia + EV"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/melate-tactico.git
git push -u origin main
```

## Desplegar en Streamlit Cloud (gratis)

1. Entra a https://share.streamlit.io y **Sign in with GitHub**.
2. **New app** → selecciona tu repositorio `melate-tactico`.
3. Rama: `main` · Main file path: `app.py`.
4. **Deploy**. En ~1–2 min obtienes una URL pública, p. ej.
   `https://melate-tactico.streamlit.app`, que puedes compartir con amigos en el celular.

Actualizaciones: haz `git push` y Streamlit Cloud redeplegará automáticamente.

## Estructura

```
melate-app/
├── app.py                 # Interfaz Streamlit (3 pestañas)
├── melate_logic.py        # Motor: generación, reglas, wheel de cobertura, EV
├── data/
│   └── melate_historico.csv
├── requirements.txt
├── .streamlit/config.toml
├── README.md
└── LICENSE
```

## Notas y advertencias

- Este proyecto es **educativo y descriptivo**: no existe sistema que aumente tu probabilidad de
  ganar un sorteo justo.
- Los montos fijos (6º–9º lugar) provienen del tabulador público de Lotería Nacional y pueden
  cambiar con cada sorteo.
- **+18. Juega responsablemente.** En México, si sientes que pierdes el control, contacta a la
  CONADIC (800 911 2000). La lotería tiene esperanza matemática negativa a largo plazo.
- No afiliado a Lotería Nacional.