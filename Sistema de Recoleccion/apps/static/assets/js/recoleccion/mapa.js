/* Mapa Leaflet de rutas de recolección con capa opcional de límites de Chile. */
window.RecoleccionMapa = (function () {
  'use strict';

  function config() {
    var meta = document.querySelector('meta[name="chile-limits-url"]');
    return {
      tileUrl: window.TICKETFLOW_MAP_TILE_URL || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
      attribution: window.TICKETFLOW_MAP_ATTRIBUTION ||
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      chileLimitsUrl: meta ? meta.getAttribute('content') : ''
    };
  }

  function numeroIcono(n) {
    var icono = L.divIcon({
      className: 'recoleccion-marcador',
      html: '<div class="recoleccion-marcador-num">' + n + '</div>',
      iconSize: [26, 26],
      iconAnchor: [13, 13]
    });
    return icono;
  }

  function inicializar(idContenedor, datos) {
    var cfg = config();
    var contenedor = document.getElementById(idContenedor);
    if (!contenedor) return;

    var mapa = L.map(contenedor);
    L.tileLayer(cfg.tileUrl, { attribution: cfg.attribution, maxZoom: 19 }).addTo(mapa);

    var grupoCapaLimites = null;
    if (cfg.chileLimitsUrl && window.L.esri && L.esri.FeatureLayer) {
      grupoCapaLimites = L.layerGroup().addTo(mapa);
      var capaLimites = L.esri.FeatureLayer({
        url: cfg.chileLimitsUrl + '/0',
        style: function () { return { color: '#8a2be2', weight: 1.2, fill: false, opacity: 0.7 }; }
      });
      grupoCapaLimites.addLayer(capaLimites);
      var alternar = document.getElementById('capa-limites');
      if (alternar) {
        alternar.addEventListener('change', function () {
          if (alternar.checked) mapa.addLayer(grupoCapaLimites);
          else mapa.removeLayer(grupoCapaLimites);
        });
      }
    }

    var limites = [];
    var marcadores = [];

    if (datos.deposito && datos.deposito.lat !== undefined) {
      L.circleMarker([datos.deposito.lat, datos.deposito.lon], {
        radius: 8, color: '#1b2a4a', weight: 2, fillColor: '#1b2a4a', fillOpacity: 1
      }).addTo(mapa).bindPopup('<strong>Depósito</strong><br>' + (datos.deposito.direccion || ''));
      limites.push([datos.deposito.lat, datos.deposito.lon]);
    }

    if (datos.geometria && datos.geometria.type === 'LineString') {
      var coordenadas = datos.geometria.coordinates.map(function (c) {
        return [c[1], c[0]];
      });
      L.polyline(coordenadas, { color: '#321fdb', weight: 4, opacity: 0.85 }).addTo(mapa);
      limites.push.apply(limites, coordenadas);
    }

    if (datos.paradas) {
      var numeros = datos.paradas.map(function (p, i) {
        return { p: p, n: i + 1 };
      });
      numeros.forEach(function (entrada) {
        var p = entrada.p;
        var color = '#321fdb';
        if (p.estado === 'completada') color = '#2eb85c';
        if (p.estado === 'no_disponible') color = '#39f';
        if (p.estado === 'incidencia') color = '#e55353';
        var marcador = L.marker([p.lat, p.lon], { icon: numeroIcono(entrada.n) }).addTo(mapa);
        marcador.setStyle = function () { };
        var popup = '<strong>' + entrada.n + '. ' + (p.numero_ticket || 'Ticket') + '</strong><br>' +
          (p.direccion || '') + '<br><span class="small">' + p.estado + '</span>';
        marcador.bindPopup(popup);
        marcadores.push(marcador);
        limites.push([p.lat, p.lon]);
      });
    }

    if (limites.length) mapa.fitBounds(L.latLngBounds(limites).pad(0.15));
    else mapa.setView([-33.45, -70.66], 12);
    return mapa;
  }

  return { inicializar: inicializar };
}());
