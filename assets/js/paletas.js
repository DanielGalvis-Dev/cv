// Selector de paletas: cambia los colores, recuerda la elección y apunta
// el botón de descarga al PDF ya generado con esa misma paleta.
(function () {
  var raiz = document.documentElement;
  var slug = document.body.dataset.slug;
  var botones = document.querySelectorAll(".paletas button");
  var descargar = document.querySelector(".descargar");

  function aplicar(p) {
    raiz.setAttribute("data-paleta", p);
    botones.forEach(function (b) {
      b.setAttribute("aria-pressed", b.dataset.p === p ? "true" : "false");
    });
    if (descargar) descargar.href = "../pdf/" + slug + "-" + p + ".pdf";
  }

  aplicar(raiz.getAttribute("data-paleta"));

  botones.forEach(function (b) {
    b.addEventListener("click", function () {
      aplicar(b.dataset.p);
      try { localStorage.setItem("paleta-" + slug, b.dataset.p); } catch (e) {}
      history.replaceState(null, "", "?paleta=" + b.dataset.p);
    });
  });
})();
