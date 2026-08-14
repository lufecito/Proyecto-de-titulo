/* API JSON del módulo de recolección (CSRF por cabecera X-CSRFToken). */
window.RecoleccionAPI = (function () {
  'use strict';

  function token() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
  }

  function peticion(method, url, cuerpo) {
    var opciones = {
      method: method,
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': token(),
        'X-Requested-With': 'XMLHttpRequest'
      }
    };
    if (cuerpo !== undefined) opciones.body = JSON.stringify(cuerpo);
    return fetch(url, opciones).then(function (respuesta) {
      return respuesta.json().catch(function () {
        return { ok: false, error: 'Respuesta no JSON (' + respuesta.status + ')' };
      }).then(function (datos) {
        if (!respuesta.ok) throw datos;
        return datos;
      });
    });
  }

  function geocodificar(direccion) {
    return peticion('POST', '/api/v1/recoleccion/geocodificar', { direccion: direccion })
      .then(function (r) { return r; });
  }

  function reversa(lat, lon) {
    return peticion('POST', '/api/v1/recoleccion/reversa', { lat: lat, lon: lon })
      .then(function (r) { return r; });
  }

  function eventoParada(paradaId, tipo, extra) {
    var cuerpo = { tipo: tipo };
    if (extra) Object.keys(extra).forEach(function (k) { cuerpo[k] = extra[k]; });
    return peticion('POST', '/api/v1/recoleccion/paradas/' + paradaId + '/evento', cuerpo)
      .then(function (r) { return r; });
  }

  function recalcular(rutaId) {
    return peticion('POST', '/api/v1/recoleccion/rutas/' + rutaId + '/recalcular', {})
      .then(function (r) { return r; });
  }

  function publicar(rutaId, versionId) {
    return peticion('POST', '/api/v1/recoleccion/rutas/' + rutaId + '/publicar',
      { version_id: versionId }).then(function (r) { return r; });
  }

  return { geocodificar: geocodificar, reversa: reversa, eventoParada: eventoParada,
           recalcular: recalcular, publicar: publicar };
}());
