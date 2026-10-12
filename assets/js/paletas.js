// Paleta de colores y ventana de descarga.
// - El selector de paletas solo aparece con ?editar (es una herramienta del dueño del CV).
// - La ventana muestra la vista previa exacta del PDF (visual o ATS) y descarga al confirmar.
(function () {
  var raiz = document.documentElement;
  var cuerpo = document.body;
  var slug = cuerpo.dataset.slug;
  var archivo = cuerpo.dataset.archivo || slug;
  var porDefecto = cuerpo.dataset.paletaDefecto;
  var params = new URLSearchParams(location.search);
  var botones = document.querySelectorAll(".paletas button");
  var abrir = document.querySelector(".barra .descargar");
  var dialogo = document.querySelector("dialog.descarga");
  var confirmar = dialogo && dialogo.querySelector(".confirmar");
  var vista = dialogo && dialogo.querySelector(".vista img");
  var vistaError = dialogo && dialogo.querySelector(".vista-error");
  var nombrePaleta = dialogo && dialogo.querySelector(".nombre-paleta");

  if (params.has("editar")) cuerpo.classList.add("editar");

  function botonDe(p) {
    var esc = window.CSS && CSS.escape ? CSS.escape(p) : String(p).replace(/[^a-z0-9-]/gi, "");
    return document.querySelector('.paletas button[data-p="' + esc + '"]');
  }

  // Si la paleta aplicada no existe (valor viejo o mal escrito), se vuelve a la de la persona.
  function paletaActual() {
    var p = raiz.getAttribute("data-paleta");
    if (!botonDe(p)) {
      p = porDefecto;
      raiz.setAttribute("data-paleta", p);
    }
    return p;
  }

  function versionElegida() {
    var marcada = dialogo.querySelector('input[name="version"]:checked');
    return marcada ? marcada.value : "visual";
  }

  function actualizarDescarga() {
    var p = paletaActual();
    if (abrir) abrir.href = "../pdf/" + slug + "-" + p + ".pdf";
    if (!dialogo) return;
    var clave = versionElegida() === "ats" ? "ats" : p;
    dialogo.querySelectorAll(".opcion").forEach(function (o) {
      o.classList.toggle("elegida", o.querySelector("input").checked);
    });
    confirmar.href = "../pdf/" + slug + "-" + clave + ".pdf";
    confirmar.setAttribute("download", archivo + (clave === "ats" ? "_ATS" : "") + ".pdf");
    vistaError.hidden = true;
    vista.hidden = false;
    vista.src = "../pdf/vistas/" + slug + "-" + clave + ".jpg";
    var boton = botonDe(p);
    if (nombrePaleta && boton) nombrePaleta.textContent = boton.title.toLowerCase();
  }

  function aplicar(p) {
    raiz.setAttribute("data-paleta", p);
    botones.forEach(function (b) {
      b.setAttribute("aria-pressed", b.dataset.p === p ? "true" : "false");
    });
    actualizarDescarga();
  }

  aplicar(paletaActual());

  botones.forEach(function (b) {
    b.addEventListener("click", function () {
      aplicar(b.dataset.p);
      try { localStorage.setItem("paleta-" + slug, b.dataset.p); } catch (e) {}
      params.set("paleta", b.dataset.p);
      history.replaceState(null, "", "?" + params.toString());
    });
  });

  // Sin <dialog> (navegadores muy viejos) el botón descarga directo el PDF visual.
  if (!dialogo || typeof dialogo.showModal !== "function") return;

  vista.addEventListener("error", function () {
    vista.hidden = true;
    vistaError.hidden = false;
  });

  abrir.addEventListener("click", function (ev) {
    // Ctrl/Cmd/Shift + clic o clic del medio: se respeta la acción del navegador.
    if (ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.altKey || ev.button !== 0) return;
    ev.preventDefault();
    dialogo.querySelector('input[value="visual"]').checked = true;
    actualizarDescarga();
    dialogo.showModal();
  });

  dialogo.querySelectorAll('input[name="version"]').forEach(function (r) {
    r.addEventListener("change", actualizarDescarga);
  });

  // Clic en el fondo cierra la ventana.
  dialogo.addEventListener("click", function (ev) {
    if (ev.target === dialogo) dialogo.close();
  });

  // Tras confirmar, la descarga sigue su curso y la ventana se cierra.
  confirmar.addEventListener("click", function () {
    setTimeout(function () { dialogo.close(); }, 150);
  });
})();
