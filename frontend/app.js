const API = "http://localhost:8000";

const ETIQUETAS_EV = {
  C: "Combinaciones posibles (C)",
  p6: "Probabilidad de 6 naturales",
  p5ad: "Probabilidad de 5 + adicional",
  p5: "Probabilidad de 5",
  p4ad: "Probabilidad de 4 + adicional",
  p4: "Probabilidad de 4",
  p3ad: "Probabilidad de 3 + adicional",
  p3: "Probabilidad de 3",
  p2ad: "Probabilidad de 2 + adicional",
  p2: "Probabilidad de 2",
  ev_fijo: "EV de premios fijos",
  ev_1er: "EV del 1er lugar",
  ev_boleto: "EV por boleto",
  ev_sesion: "EV de la sesión",
  prob_ganar_algo: "Probabilidad de ganar algo",
  bolsa: "Bolsa",
  precio: "Precio por boleto",
  ganadores: "Ganadores esperados del 1er lugar",
  tickets: "Boletos comprados",
  break_even: "Bote de equilibrio",
};

const CAMPOS_DINERO = ["ev_fijo", "ev_1er", "ev_boleto", "ev_sesion", "bolsa", "precio", "break_even"];
const CAMPOS_ENTEROS = ["C", "ganadores", "tickets"];
const CAMPOS_PROBABILIDAD = ["p6", "p5ad", "p5", "p4ad", "p4", "p3ad", "p3", "p2ad", "p2"];

function porId(id) {
  return document.getElementById(id);
}

function mostrarError(mensaje) {
  const banner = porId("banner");
  banner.textContent = mensaje;
  banner.hidden = false;
}

function limpiarError() {
  const banner = porId("banner");
  banner.textContent = "";
  banner.hidden = true;
}

async function pedir(ruta, opciones) {
  const opcionesFinales = Object.assign({ credentials: "include" }, opciones || {});
  const respuesta = await fetch(API + ruta, opcionesFinales);
  let datos = null;
  try {
    datos = await respuesta.json();
  } catch (error) {
    datos = null;
  }
  if (!respuesta.ok) {
    const mensaje = datos && datos.error ? datos.error : "No se pudo completar la solicitud.";
    const error = new Error(mensaje);
    error.status = respuesta.status;
    throw error;
  }
  return datos;
}

function mostrarLogin() {
  porId("auth-login").hidden = false;
  porId("auth-sesion").hidden = true;
}

function mostrarSesion(usuario) {
  porId("auth-email").textContent = usuario.email;
  porId("auth-sesion").hidden = false;
  porId("auth-login").hidden = true;
}

async function cargarSesion() {
  try {
    const usuario = await pedir("/api/auth/me");
    mostrarSesion(usuario);
    return true;
  } catch (error) {
    mostrarLogin();
    if (error.status !== 401) {
      mostrarError(error.message);
    }
    return false;
  }
}

function mostrarErrorSolicitud(error) {
  if (error.status === 401) {
    mostrarError("Inicia sesión para continuar");
    mostrarLogin();
  } else {
    mostrarError(error.message);
  }
}

async function cerrarSesion() {
  try {
    await pedir("/api/auth/logout", { method: "POST" });
    window.location.reload();
  } catch (error) {
    mostrarError(error.message);
  }
}

function iniciarLogin() {
  window.location.assign(API + "/api/auth/login");
}

function numero(valor, decimales) {
  return Number(valor).toLocaleString("es-MX", {
    minimumFractionDigits: decimales || 0,
    maximumFractionDigits: decimales || 0,
  });
}

function dinero(valor) {
  return "$" + numero(valor, 2);
}

function activarTab(nombre) {
  document.querySelectorAll(".tab").forEach(function (boton) {
    const activo = boton.dataset.tab === nombre;
    boton.classList.toggle("activo", activo);
    boton.setAttribute("aria-selected", activo ? "true" : "false");
  });
  document.querySelectorAll(".panel").forEach(function (panel) {
    panel.hidden = panel.id !== nombre;
  });
}

async function cargarReglas() {
  try {
    const reglas = await pedir("/api/reglas/default");
    porId("min_altos").value = reglas.min_altos;
    porId("no_consecutivos").checked = Boolean(reglas.no_consecutivos);
    porId("no_digitos_repetidos").checked = Boolean(reglas.no_digitos_repetidos);
    porId("min_decanas").checked = Number(reglas.min_decanas) >= 4;
    porId("no_secuencias_aritmeticas").checked = Boolean(reglas.no_secuencias_aritmeticas);
    porId("columnas").checked = Boolean(reglas.columnas);
  } catch (error) {
    mostrarError(error.message);
  }
}

function crearTarjeta(titulo, valor) {
  const tarjeta = document.createElement("div");
  tarjeta.className = "tarjeta";
  const etiqueta = document.createElement("strong");
  etiqueta.textContent = titulo;
  const contenido = document.createElement("span");
  contenido.textContent = valor;
  tarjeta.append(etiqueta, contenido);
  return tarjeta;
}

function renderTickets(datos) {
  const contenedor = porId("resultado-tickets");
  contenedor.innerHTML = "";
  contenedor.hidden = false;

  const titulo = document.createElement("h3");
  titulo.textContent = "Tus boletos";

  const costo = document.createElement("p");
  costo.className = "costo";
  costo.textContent =
    datos.tickets.length + " boletos × $15 = " + dinero(datos.tickets.length * 15) + " MXN por sorteo.";

  contenedor.append(titulo, costo);

  datos.tickets.forEach(function (ticket, indice) {
    const caja = document.createElement("article");
    caja.className = "ticket";

    const encabezado = document.createElement("p");
    encabezado.className = "ticket-titulo";
    encabezado.textContent = "Boleto " + (indice + 1);

    const fila = document.createElement("div");
    fila.className = "ticket-num";
    ticket.forEach(function (bola) {
      const esfera = document.createElement("span");
      esfera.className = "bola";
      esfera.textContent = String(bola).padStart(2, "0");
      fila.appendChild(esfera);
    });

    const lista = document.createElement("ul");
    lista.className = "reglas";
    const reglasTicket = datos.reglas[indice] || [];
    reglasTicket.forEach(function (regla) {
      const item = document.createElement("li");
      item.className = "regla";
      const etiqueta = document.createElement("span");
      etiqueta.textContent = regla.label;
      const estado = document.createElement("span");
      estado.className = regla.cumple ? "estado-ok" : "estado-fail";
      estado.textContent = regla.cumple ? "Cumple" : "No cumple";
      item.append(etiqueta, estado);
      lista.appendChild(item);
    });

    caja.append(encabezado, fila, lista);
    contenedor.appendChild(caja);
  });
}

async function generarTickets(evento) {
  evento.preventDefault();
  limpiarError();

  const cuerpo = {
    n: Number(porId("n").value),
    rules: {
      min_altos: Number(porId("min_altos").value),
      no_consecutivos: porId("no_consecutivos").checked,
      no_digitos_repetidos: porId("no_digitos_repetidos").checked,
      min_decanas: porId("min_decanas").checked ? 4 : 0,
      no_secuencias_aritmeticas: porId("no_secuencias_aritmeticas").checked,
      columnas: porId("columnas").checked,
    },
  };

  const semilla = porId("seed").value.trim();
  if (semilla !== "") {
    cuerpo.seed = Number(semilla);
  }

  const boton = evento.target.querySelector("button[type=submit]");
  boton.disabled = true;
  try {
    const datos = await pedir("/api/tickets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cuerpo),
    });
    renderTickets(datos);
  } catch (error) {
    mostrarErrorSolicitud(error);
  } finally {
    boton.disabled = false;
  }
}

function renderHistorico(datos) {
  const contenedor = porId("historico");
  contenedor.innerHTML = "";

  const resumen = document.createElement("div");
  resumen.className = "resumen";
  resumen.append(
    crearTarjeta("Total de sorteos", numero(datos.total_sorteos)),
    crearTarjeta("Desde", datos.rango_fechas.desde),
    crearTarjeta("Hasta", datos.rango_fechas.hasta),
    crearTarjeta("Racha actual", numero(datos.streak_actual) + " sorteos"),
    crearTarjeta("Periodo de bote alto", datos.periodo_bote_alto ? "Sí" : "No"),
    crearTarjeta("Bolsa mínima", dinero(datos.estadisticas_bolsa.min)),
    crearTarjeta("Bolsa máxima", dinero(datos.estadisticas_bolsa.max)),
    crearTarjeta("Bolsa media", dinero(datos.estadisticas_bolsa.media)),
    crearTarjeta("Bolsa mediana", dinero(datos.estadisticas_bolsa.mediana))
  );

  const subtitulo = document.createElement("h3");
  subtitulo.textContent = "Últimos 10 sorteos";

  const tabla = document.createElement("table");
  tabla.className = "tabla";
  const cabeza = document.createElement("thead");
  const filaCabeza = document.createElement("tr");
  ["Concurso", "Fecha", "Bolsa"].forEach(function (texto) {
    const celda = document.createElement("th");
    celda.textContent = texto;
    filaCabeza.appendChild(celda);
  });
  cabeza.appendChild(filaCabeza);

  const cuerpo = document.createElement("tbody");
  datos.ultimos_sorteos.forEach(function (sorteo) {
    const fila = document.createElement("tr");
    [numero(sorteo.concurso), sorteo.fecha, dinero(sorteo.bolsa)].forEach(function (valor) {
      const celda = document.createElement("td");
      celda.textContent = valor;
      fila.appendChild(celda);
    });
    cuerpo.appendChild(fila);
  });

  tabla.append(cabeza, cuerpo);
  contenedor.append(resumen, subtitulo, tabla);
}

async function cargarHistorico() {
  const contenedor = porId("historico");
  try {
    const datos = await pedir("/api/historico");
    renderHistorico(datos);
    if (datos.ultimos_sorteos.length > 0) {
      porId("bolsa").value = datos.ultimos_sorteos[datos.ultimos_sorteos.length - 1].bolsa;
    }
  } catch (error) {
    if (error.status === 401) {
      contenedor.textContent = "Inicia sesión para ver el histórico.";
      mostrarLogin();
    } else {
      contenedor.textContent = "No se pudo cargar el histórico.";
      mostrarError(error.message);
    }
  }
}

function formatearValorEv(clave, valor) {
  if (clave === "prob_ganar_algo") {
    return "1 en " + numero(1 / valor, 1);
  }
  if (CAMPOS_PROBABILIDAD.indexOf(clave) !== -1) {
    return "1 en " + numero(1 / valor, 0);
  }
  if (CAMPOS_DINERO.indexOf(clave) !== -1) {
    return dinero(valor);
  }
  if (CAMPOS_ENTEROS.indexOf(clave) !== -1) {
    return numero(valor);
  }
  return numero(valor, 4);
}

function renderEv(datos) {
  const contenedor = porId("resultado-ev");
  contenedor.innerHTML = "";
  contenedor.hidden = false;

  const titulo = document.createElement("h3");
  titulo.textContent = "Resultados";

  const tabla = document.createElement("table");
  tabla.className = "tabla";
  const cuerpo = document.createElement("tbody");
  Object.keys(datos).forEach(function (clave) {
    const fila = document.createElement("tr");
    const etiqueta = document.createElement("th");
    etiqueta.textContent = ETIQUETAS_EV[clave] || clave;
    const valor = document.createElement("td");
    valor.textContent = formatearValorEv(clave, datos[clave]);
    fila.append(etiqueta, valor);
    cuerpo.appendChild(fila);
  });
  tabla.appendChild(cuerpo);

  const nota = document.createElement("p");
  nota.className = "costo";
  if (datos.ev_boleto >= datos.precio) {
    nota.textContent =
      "EV alto: el boleto tiene esperanza positiva en teoría. Con botes récord más gente juega y el reparto crece.";
  } else {
    nota.textContent =
      "Con botes normales el boleto tiene esperanza negativa: costo mayor o igual al EV. Se juega por entretenimiento, no como inversión.";
  }

  contenedor.append(titulo, tabla, nota);
}

async function calcularEv(evento) {
  evento.preventDefault();
  limpiarError();

  const cuerpo = {
    bolsa: Number(porId("bolsa").value),
    precio: Number(porId("precio").value),
    ganadores: Number(porId("ganadores").value),
    tickets: Number(porId("tickets").value),
  };

  const boton = evento.target.querySelector("button[type=submit]");
  boton.disabled = true;
  try {
    const datos = await pedir("/api/ev", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cuerpo),
    });
    renderEv(datos);
  } catch (error) {
    mostrarErrorSolicitud(error);
  } finally {
    boton.disabled = false;
  }
}

document.querySelectorAll(".tab").forEach(function (boton) {
  boton.addEventListener("click", function () {
    activarTab(boton.dataset.tab);
  });
});

porId("form-generar").addEventListener("submit", generarTickets);
porId("form-ev").addEventListener("submit", calcularEv);
porId("btn-login").addEventListener("click", iniciarLogin);
porId("btn-logout").addEventListener("click", cerrarSesion);

async function iniciar() {
  await cargarReglas();
  const autenticado = await cargarSesion();
  if (autenticado) {
    await cargarHistorico();
  } else {
    porId("historico").textContent = "Inicia sesión para ver el histórico.";
  }
  const parametros = new URLSearchParams(window.location.search);
  if (parametros.get("auth") === "error") {
    mostrarError("No se pudo iniciar sesión con Google. Intenta de nuevo.");
    window.history.replaceState({}, "", window.location.pathname);
  }
}

iniciar();
