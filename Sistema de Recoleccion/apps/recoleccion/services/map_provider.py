# -*- encoding: utf-8 -*-
"""
Adaptador cartográfico desacoplado (arquitectura híbrida).

- MapProvider: interfaz propia (geocodificación, matriz, geometría).
- OpenRouteServiceProvider: proveedor real; la clave viaja solo en el
  encabezado Authorization y nunca llega al navegador.
- FakeMapProvider: modo demostración sin red, con distancias explícitamente
  etiquetadas como estimación NO vial.

Errores: MapProviderError con `kind` para clasificar autenticación, cuota,
timeout, red o validación. Reintentos solo para estados transitorios.
"""

import hashlib
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict

import requests

from apps.recoleccion.services.geocache import MapCache, cache_key

# Version de la interfaz de proveedores (participa en la clave de caché).
MAP_PROVIDER_INTERFACE_VERSION = '1'


class MapProviderError(Exception):
    """Error controlado del proveedor cartográfico."""

    def __init__(self, mensaje, kind='provider', http_status=None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.kind = kind
        self.http_status = http_status


@dataclass
class GeocodeResult:
    lat: float
    lon: float
    direccion_normalizada: str
    proveedor: str
    precision: str
    comuna: str = ''
    region: str = ''
    cacheado: bool = False

    def to_dict(self):
        return asdict(self)


@dataclass
class MatrixResult:
    duraciones: list  # segundos, fila i -> columna j
    distancias: list  # metros
    coords: list  # [(lat, lon)]
    proveedor: str
    perfil: str
    estimacion_vial: bool = True
    cacheado: bool = False


class MapProvider(ABC):
    provider_name = 'base'
    version = '0'
    modo_demo = False
    is_configured = True

    @abstractmethod
    def geocode(self, direccion):
        raise NotImplementedError

    @abstractmethod
    def reverse_geocode(self, lat, lon):
        raise NotImplementedError

    @abstractmethod
    def matrix(self, coords, perfil=None):
        raise NotImplementedError

    @abstractmethod
    def route_geometry(self, coords, perfil=None):
        raise NotImplementedError

    def status_info(self):
        return {
            'nombre': self.provider_name,
            'version': self.version,
            'configurado': self.is_configured,
            'demo': self.modo_demo,
        }


def decode_polyline5(polyline):
    """Decodifica polilínea Google (precisión 5, factor 1e5) a [(lat, lon)]."""
    coords = []
    index = 0
    lat = 0
    lon = 0
    while index < len(polyline):
        result = shift = 0
        while True:
            b = ord(polyline[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20:
                break
        lat += ~(result >> 1) if result & 1 else (result >> 1)
        result = shift = 0
        while True:
            b = ord(polyline[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20:
                break
        lon += ~(result >> 1) if result & 1 else (result >> 1)
        coords.append((lat / 1e5, lon / 1e5))
    return coords


class OpenRouteServiceProvider(MapProvider):
    provider_name = 'openrouteservice'
    version = 'v2'
    is_configured = True
    modo_demo = False

    def __init__(self, config):
        self.config = config
        self.api_key = (config.get('ORS_API_KEY') or '').strip()
        self.base_url = (config.get('ORS_BASE_URL') or 'https://api.openrouteservice.org').rstrip('/')
        self.geocode_base = (config.get('ORS_GEOCODE_BASE_URL')
                             or 'https://api.openrouteservice.org/geocode').rstrip('/')
        self.profile_default = config.get('ORS_PROFILE') or 'driving-hgv'
        self.country = config.get('ORS_GEOCODE_COUNTRY') or 'CHL'
        self.timeout = float(config.get('MAP_HTTP_TIMEOUT_SECONDS') or 15)
        self.retries = int(config.get('MAP_HTTP_RETRIES') or 2)
        self.max_response_bytes = int(config.get('ORS_MAX_RESPONSE_BYTES') or 2000000)
        self.cache = MapCache(
            config.get('MAP_CACHE_DIR') or 'map_cache',
            ttl_segundos=int(config.get('MATRIX_CACHE_TTL_SECONDS') or 604800),
            max_entradas=int(config.get('MAP_CACHE_MAX_ENTRIES') or 2000),
        )

    def _headers(self):
        return {'Authorization': self.api_key}

    def _request(self, method, url, params=None, payload=None):
        backoff = 0.4
        last = None
        for intento in range(self.retries + 1):
            try:
                respuesta = requests.request(
                    method, url, params=params, json=payload,
                    headers=self._headers(), timeout=self.timeout)
            except requests.exceptions.Timeout:
                last = MapProviderError(
                    'Tiempo de espera del proveedor cartográfico agotado.', kind='timeout')
            except requests.exceptions.RequestException as exc:
                last = MapProviderError(
                    f'Proveedor cartográfico no disponible ({exc.__class__.__name__}).',
                    kind='network')
            else:
                if respuesta.status_code in (429, 500, 502, 503, 504):
                    if respuesta.status_code == 429 and intento >= self.retries:
                        raise MapProviderError(
                            'Cuota del proveedor cartográfico agotada.', kind='quota',
                            http_status=429)
                    if intento >= self.retries:
                        raise MapProviderError(
                            f'Proveedor cartográfico devolvió estado {respuesta.status_code}.',
                            kind='provider', http_status=respuesta.status_code)
                    last = None
                elif respuesta.status_code in (401, 403):
                    raise MapProviderError(
                        'Autenticación del proveedor cartográfico fallida.', kind='auth',
                        http_status=respuesta.status_code)
                elif respuesta.status_code >= 400:
                    raise MapProviderError(
                        f'Petición cartográfica rechazada ({respuesta.status_code}).',
                        kind='validation', http_status=respuesta.status_code)
                elif len(respuesta.content) > self.max_response_bytes:
                    raise MapProviderError(
                        'Respuesta cartográfica excede el límite de tamaño.', kind='provider')
                else:
                    return respuesta
            if last is not None:
                if intento >= self.retries:
                    raise last
                time.sleep(backoff)
                backoff *= 2
        raise last or MapProviderError('Error desconocido del proveedor cartográfico.',
                                       kind='provider')

    def geocode(self, direccion):
        texto = (direccion or '').strip()
        if not texto:
            raise MapProviderError('Dirección vacía.', kind='validation')
        key = cache_key('geocode', self.provider_name, MAP_PROVIDER_INTERFACE_VERSION,
                        self.country, texto)
        datos = self.cache.get(key)
        if datos is not None:
            return GeocodeResult(**datos, cacheado=True)
        respuesta = self._request(
            'GET', f'{self.geocode_base}/search',
            params={'text': texto, 'size': 1, 'boundary.country': self.country})
        try:
            data = respuesta.json()
        except ValueError:
            raise MapProviderError('Respuesta cartográfica inválida.', kind='provider')
        features = data.get('features') or []
        if not features:
            raise MapProviderError(
                'La dirección no pudo geocodificarse; corríjala o ingrese coordenadas manualmente.',
                kind='validation')
        coords = features[0].get('geometry', {}).get('coordinates')
        if not coords:
            raise MapProviderError('Respuesta cartográfica sin coordenadas.', kind='provider')
        props = features[0].get('properties', {}) or {}
        resultado = GeocodeResult(
            lat=float(coords[1]), lon=float(coords[0]),
            direccion_normalizada=(props.get('label') or props.get('name') or texto),
            proveedor=self.provider_name,
            precision=_precisión_ors(props.get('layer') or 'address'),
            comuna=props.get('locality') or '',
            region=props.get('region') or '',
        )
        self.cache.set(key, resultado.to_dict())
        return resultado

    def reverse_geocode(self, lat, lon):
        key = cache_key('reverse', self.provider_name, MAP_PROVIDER_INTERFACE_VERSION,
                        f'{lat:.6f}', f'{lon:.6f}')
        datos = self.cache.get(key)
        if datos is not None:
            return GeocodeResult(**datos, cacheado=True)
        respuesta = self._request(
            'GET', f'{self.geocode_base}/reverse',
            params={'point.lon': lon, 'point.lat': lat, 'size': 1})
        try:
            data = respuesta.json()
        except ValueError:
            raise MapProviderError('Respuesta cartográfica inválida.', kind='provider')
        features = data.get('features') or []
        if not features:
            raise MapProviderError('Sin resultados de geocodificación inversa.',
                                   kind='validation')
        coords = features[0].get('geometry', {}).get('coordinates')
        props = features[0].get('properties', {}) or {}
        resultado = GeocodeResult(
            lat=float(lat), lon=float(lon),
            direccion_normalizada=(props.get('label') or 'Ubicación sin dirección'),
            proveedor=self.provider_name,
            precision='punto',
            comuna=props.get('locality') or '',
            region=props.get('region') or '',
        )
        self.cache.set(key, resultado.to_dict())
        return resultado

    def matrix(self, coords, perfil=None):
        perfil = perfil or self.profile_default
        pares = '|'.join(sorted(f'{a:.6f},{b:.6f}' for a, b in coords))
        key = cache_key('matrix', self.provider_name, MAP_PROVIDER_INTERFACE_VERSION,
                        perfil, pares)
        datos = self.cache.get(key)
        if datos is not None:
            return MatrixResult(**datos, cacheado=True)
        locations = [[lon, lat] for lat, lon in coords]
        respuesta = self._request(
            'POST', f'{self.base_url}/v2/matrix/{perfil}',
            payload={'locations': locations, 'metrics': ['duration', 'distance']})
        try:
            data = respuesta.json()
        except ValueError:
            raise MapProviderError('Respuesta de matriz inválida.', kind='provider')
        duraciones = _normalizar_matriz(data.get('durations'))
        distancias = _normalizar_matriz(data.get('distances'))
        resultado = MatrixResult(duraciones, distancias, list(coords),
                                 proveedor=self.provider_name, perfil=perfil)
        self.cache.set(key, {
            'duraciones': duraciones, 'distancias': distancias,
            'coords': list(coords), 'proveedor': self.provider_name, 'perfil': perfil,
        })
        return resultado

    def route_geometry(self, coords, perfil=None):
        perfil = perfil or self.profile_default
        locations = [[lon, lat] for lat, lon in coords]
        respuesta = self._request(
            'POST', f'{self.base_url}/v2/directions/{perfil}?format=geojson',
            payload={'coordinates': locations, 'geometry': True,
                     'instructions': False, 'elevation': False})
        try:
            data = respuesta.json()
        except ValueError:
            raise MapProviderError('Respuesta de geometría inválida.', kind='provider')
        features = data.get('features') or []
        if features:
            geometry = features[0].get('geometry')
            if isinstance(geometry, dict) and geometry.get('type') == 'LineString':
                return geometry
        route = (data.get('routes') or [None])[0]
        if route and isinstance(route.get('geometry'), str):
            polilinea = route['geometry']
            coords_decoded = decode_polyline5(polilinea)
            return {'type': 'LineString',
                    'coordinates': [[lon, lat] for lat, lon in coords_decoded]}
        raise MapProviderError('No se pudo obtener la geometría de la ruta.',
                               kind='validation')


def _precisión_ors(capa):
    capa = (capa or '').lower()
    if capa in ('address', 'venue', 'poi'):
        return 'punto'
    if capa == 'street':
        return 'calle'
    if capa in ('locality', 'county', 'macrocounty'):
        return 'ciudad'
    if capa in ('region', 'macroregion', 'country'):
        return 'region'
    return 'punto'


def _normalizar_matriz(matriz):
    """Reemplaza pares inalcanzables (null) por un valor muy alto."""
    grande = 3600 * 24 * 365.0
    return [
        [grande if valor is None else float(valor) for valor in fila]
        for fila in (matriz or [])
    ]


class FakeMapProvider(MapProvider):
    """
    Proveedor de demostración sin red. Las distancias son una estimación
    sintética NO vial (no corresponden a la red de calles).
    """
    provider_name = 'fake'
    version = '1.0'
    is_configured = False
    modo_demo = True

    CENTRO = (-33.4372, -70.6506)
    _radios = 0.06

    def __init__(self, config=None):
        self.config = config or {}

    def geocode(self, direccion):
        texto = (direccion or '').strip()
        if not texto:
            raise MapProviderError('Dirección vacía.', kind='validation')
        lat, lon = self._pseudo_coords(texto)
        return GeocodeResult(lat, lon, direccion_normalizada=texto,
                             proveedor='fake', precision='punto')

    def reverse_geocode(self, lat, lon):
        return GeocodeResult(float(lat), float(lon),
                             direccion_normalizada='Ubicación manual de demostración',
                             proveedor='fake', precision='punto')

    def matrix(self, coords, perfil=None):
        n = len(coords)
        distancias = [[0.0] * n for _ in range(n)]
        duraciones = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                d = self._distancia_sintetica(coords[i], coords[j])
                distancias[i][j] = d
                duraciones[i][j] = d / 8.0  # ~28,8 km/h
        return MatrixResult(duraciones, distancias, list(coords),
                            proveedor='fake', perfil=perfil or 'driving-hgv',
                            estimacion_vial=False)

    def route_geometry(self, coords, perfil=None):
        return {'type': 'LineString',
                'coordinates': [[lon, lat] for lat, lon in coords]}

    @classmethod
    def _pseudo_coords(cls, texto):
        digesto = hashlib.sha256(texto.encode('utf-8')).digest()
        lat = cls.CENTRO[0] + (digesto[0] / 255.0 - 0.5) * 2 * cls._radios
        lon = cls.CENTRO[1] + (digesto[1] / 255.0 - 0.5) * 2 * cls._radios
        return round(lat, 6), round(lon, 6)

    @staticmethod
    def _distancia_sintetica(a, b):
        """Manhattan con factor de rodeo. Estimación NO vial."""
        lat1, lon1 = a
        lat2, lon2 = b
        dx = (lon2 - lon1) * 111320.0
        dy = (lat2 - lat1) * 110574.0
        return round((abs(dx) + abs(dy)) * 1.25, 1)

    def status_info(self):
        return {
            'nombre': self.provider_name,
            'version': self.version,
            'configurado': False,
            'demo': True,
        }


_provider_cache = {}


def get_map_provider():
    """Fabrica el proveedor según la configuración de la aplicación."""
    from flask import current_app
    cfg = current_app.config
    override = cfg.get('MAP_PROVIDER_OVERRIDE')
    if override is not None:
        return override
    firma = (
        cfg.get('MAP_PROVIDER'), cfg.get('ORS_API_KEY'),
        cfg.get('ORS_BASE_URL'), cfg.get('ORS_GEOCODE_BASE_URL'),
        cfg.get('MAP_CACHE_DIR'),
    )
    if firma in _provider_cache:
        return _provider_cache[firma]
    modo = (cfg.get('MAP_PROVIDER') or 'auto').strip().lower()
    api_key = (cfg.get('ORS_API_KEY') or '').strip()
    if modo == 'ors' or (modo == 'auto' and api_key):
        proveedor = OpenRouteServiceProvider(cfg)
    else:
        proveedor = FakeMapProvider(cfg)
    _provider_cache[firma] = proveedor
    return proveedor


def provider_status():
    """Estado legible del proveedor para la interfaz."""
    try:
        proveedor = get_map_provider()
        info = proveedor.status_info()
        if proveedor.modo_demo:
            mensaje = ('Proveedor cartográfico no configurado. Modo demostración con '
                       'estimaciones NO viales; ingrese coordenadas o configure ORS_API_KEY.')
            nivel = 'warning'
        elif not proveedor.is_configured:
            mensaje = 'Proveedor cartográfico no configurado.'
            nivel = 'warning'
        else:
            mensaje = f'Proveedor cartográfico configurado ({proveedor.provider_name}).'
            nivel = 'ok'
        return {**info, 'mensaje': mensaje, 'nivel': nivel}
    except MapProviderError as exc:
        return {'nombre': 'desconocido', 'configurado': False, 'demo': False,
                'mensaje': exc.mensaje, 'nivel': 'error'}
