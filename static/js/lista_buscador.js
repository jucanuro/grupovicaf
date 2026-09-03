/* lista_buscador.js — filtro en vivo, server-rendered, para las listas del LIMS.
 *
 * En la plantilla de la lista:
 *   - un contenedor  [data-lista-contenedor][data-lista-url="{% url '...' %}"]
 *     cuyo innerHTML es el PARCIAL de la tabla (thead + tbody + footer +
 *     tarjetas mobile). Nada de búsqueda va adentro de este contenedor.
 *   - uno o más inputs  [data-lista-buscador]  FUERA del contenedor.
 *     El del encabezado lo pone cabecera_base.html cuando la vista pasa
 *     `header_search = {'id': ..., 'placeholder': ...}`.
 *
 * La vista PUEDE devolver solo ese parcial cuando el request trae
 * `X-Requested-With: XMLHttpRequest` (más liviano). Si devuelve la página
 * completa, este módulo igual extrae el [data-lista-contenedor] de la
 * respuesta — así una lista funciona con o sin el parcial en la vista.
 *
 * Tras cada refresco emite `lista:actualizada` en el contenedor, para que la
 * página re-inicialice tooltips / iconos / lo que haga falta sobre las filas
 * nuevas.
 */
(function () {
  "use strict";

  function init() {
    var contenedor = document.querySelector("[data-lista-contenedor]");
    var inputs = Array.prototype.slice.call(
      document.querySelectorAll("[data-lista-buscador]")
    );
    if (!contenedor || !inputs.length) return;

    var baseUrl = contenedor.getAttribute("data-lista-url");
    if (!baseUrl) return;

    var timer = null;

    function sanear(v) {
      return v.replace(/[<>]/g, "").slice(0, 100);
    }

    function sincronizar(valor, excepto) {
      inputs.forEach(function (i) {
        if (i !== excepto) i.value = valor;
      });
    }

    function construirUrl(termino, origen) {
      // Si el input vive dentro de un <form> de filtros, arrastramos el resto
      // de sus campos (estado, fechas, ...) para no perderlos al buscar.
      var form = origen && origen.closest ? origen.closest("form") : null;
      var params = form ? new URLSearchParams(new FormData(form)) : new URLSearchParams();
      params.set("q", termino);
      params.delete("page");
      var sep = baseUrl.indexOf("?") === -1 ? "?" : "&";
      return baseUrl + sep + params.toString();
    }

    function refrescar(termino, origen) {
      var url = construirUrl(termino, origen);

      contenedor.classList.add("lista-cargando");
      fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } })
        .then(function (r) {
          if (!r.ok) throw new Error("HTTP " + r.status);
          return r.text();
        })
        .then(function (html) {
          if (/<html[\s>]/i.test(html)) {
            // Respuesta = página completa: extraer solo el contenedor.
            var doc = new DOMParser().parseFromString(html, "text/html");
            var nuevo = doc.querySelector("[data-lista-contenedor]");
            contenedor.innerHTML = nuevo ? nuevo.innerHTML : contenedor.innerHTML;
          } else {
            // Respuesta = parcial de la tabla.
            contenedor.innerHTML = html;
          }
        })
        .catch(function (err) {
          console.error("lista_buscador:", err);
        })
        .then(function () {
          contenedor.classList.remove("lista-cargando");
          if (window.lucide && window.lucide.createIcons) window.lucide.createIcons();
          contenedor.dispatchEvent(
            new CustomEvent("lista:actualizada", { bubbles: true })
          );
        });
    }

    inputs.forEach(function (input) {
      input.addEventListener("input", function (e) {
        var valor = sanear(e.target.value);
        if (e.target.value !== valor) e.target.value = valor;
        sincronizar(valor, e.target);
        clearTimeout(timer);
        timer = setTimeout(function () {
          refrescar(valor, e.target);
        }, 300);
      });

      // Esc: limpia el filtro y vuelve a la lista completa.
      input.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && input.value !== "") {
          e.preventDefault();
          e.stopPropagation();
          sincronizar("", null);
          clearTimeout(timer);
          refrescar("", input);
        }
      });

      // Si el input vive dentro de un <form> (búsqueda vieja por GET), que
      // ENTER no recargue: dispara el mismo refresco AJAX.
      var form = input.closest ? input.closest("form") : null;
      if (form && !form.getAttribute("data-lista-buscador-form")) {
        form.setAttribute("data-lista-buscador-form", "1");
        form.addEventListener("submit", function (e) {
          e.preventDefault();
          clearTimeout(timer);
          refrescar(sanear(input.value), input);
        });
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
