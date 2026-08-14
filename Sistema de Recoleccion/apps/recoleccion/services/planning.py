# -*- encoding: utf-8 -*-
"""
PlanificaciÃ³n: reglas de negocio que conectan las entidades de recolecciÃ³n
con el adaptador cartogrÃ¡fico y el optimizador local.

Responsabilidades separadas:
- ConstrucciÃ³n del problema (stops, vehÃ­culos, matriz).
- EjecuciÃ³n de la lÃ­nea base y de la propuesta optimizada.
- Persistencia de versiones (lÃ­nea base, propuesta, publicada) y de
  ejecuciones de optimizaciÃ³n.
- Recalculo que conserva las paradas completadas.
- PublicaciÃ³n inmutable de una versiÃ³n.
"""

import json
from datetime import timedelta

from flask_login import current_user

from apps import db


def _usuario_actual():
    """Usuario autenticado en el contexto actual, o None fuera de request."""
    try:
        if current_user is not None and current_user.is_authenticated:
            return current_user
    except Exception:
        pass
    return None
from apps.recoleccion.models import (
    EjecucionOptimizacion, EventoRuta, Jornada, ParadaRuta, Ruta, RutaVersion,
    SolicitudRecoleccion, as_utc, utcnow,
)
from apps.recoleccion.services.map_provider import (
    MapProviderError, get_map_provider, provider_status,
)
from apps.recoleccion.services.optimizer import (
    MatrixData, NearestNeighborBaseline, OptimizationParameters,
    ORToolsVRPOptimizer, Stop, Vehicle, _buscar_indice_coordenada,
    _costos_orden, hash_entrada_optimizacion, resultado_a_json,
)

GEOMETRIA_MAX_BYTES = 200000
ESTADOS_OPTIMIZABLES = ('pendiente', 'disponible', 'asignada')


def parametros_optimizacion(cfg=None):
    """ParÃ¡metros del optimizador desde la configuraciÃ³n de la aplicaciÃ³n."""
    from flask import current_app
    cfg = cfg or current_app.config
    return OptimizationParameters(
        limite_tiempo_segundos=int(cfg.get('OPTIMIZER_TIME_LIMIT_SECONDS') or 30))


def _solicitudes_optimizables(jornada):
    resultado = []
    for sol in jornada.solicitudes:
        if sol.estado_operacional not in ESTADOS_OPTIMIZABLES:
            continue
        if sol.estado_disponibilidad != 'disponible':
            continue
        punto = sol.punto
        if (not punto or punto.estado_validacion != 'validado'
                or punto.latitud is None or punto.longitud is None):
            continue
        resultado.append(sol)
    return sorted(resultado, key=lambda s: (s.prioridad, s.id))


def _segundos_desde_inicio(jornada, valor):
    if valor is None:
        return None
    delta = as_utc(valor) - as_utc(jornada.inicio_operacion)
    return delta.total_seconds()


def construir_problema(jornada, perfil=None):
    """Construye stops, vehÃ­culos y matriz de la jornada."""
    proveedor = get_map_provider()
    perfil = perfil or (jornada.vehiculos[0].perfil_ruteo
                        if jornada.vehiculos else proveedor.config.get(
                            'ORS_PROFILE') if isinstance(proveedor.config, dict)
                        else 'driving-hgv') or 'driving-hgv'

    solicitudes = _solicitudes_optimizables(jornada)
    coords = [(jornada.deposito_lat, jornada.deposito_lon)]
    coords += [(s.punto.latitud, s.punto.longitud) for s in solicitudes]
    matriz = proveedor.matrix(coords, perfil)

    stops = []
    for sol in solicitudes:
        stops.append(Stop(
            id=f'sol_{sol.id}',
            demanda=sol.demanda or 0,
            duracion_servicio=sol.duracion_servicio_seg or 0,
            prioridad=sol.prioridad or 3,
            ventana_inicio=_segundos_desde_inicio(jornada, sol.ventana_inicio),
            ventana_fin=_segundos_desde_inicio(jornada, sol.ventana_fin),
            lat=sol.punto.latitud,
            lon=sol.punto.longitud,
        ))

    vehiculos = [
        Vehicle(id=f'veh_{v.id}', capacidad=v.capacidad or 0, perfil=v.perfil_ruteo,
                lat_inicio=v.lat_inicio, lon_inicio=v.lon_inicio,
                lat_fin=v.lat_fin, lon_fin=v.lon_fin)
        for v in jornada.vehiculos
        if v.estado_disponibilidad == 'disponible'
    ]
    datos_matriz = MatrixData(
        coords=matriz.coords, duraciones=matriz.duraciones,
        distancias=matriz.distancias, proveedor=matriz.proveedor,
        perfil=matriz.perfil, estimacion_vial=matriz.estimacion_vial)
    return stops, vehiculos, datos_matriz, proveedor, perfil


def _crear_version(ruta, tipo, asignacion, stops_por_id, matrix, params,
                   resultado, usuario, proveedor, perfil, no_asignadas_global,
                   jornada):
    """Crea una RutaVersion con sus paradas a partir de una asignaciÃ³n."""
    numero = _siguiente_numero_version(ruta)
    indice_parada = {}
    for stop_id in asignacion:
        stop = stops_por_id[stop_id]
        idx = _buscar_indice_coordenada(matrix, stop.lat, stop.lon)
        if idx is not None:
            indice_parada[stop_id] = idx

    coords_orden = [0] + [indice_parada[s] for s in asignacion] + [0]
    servicio_por_nodo = {indice_parada[s.id]: s.duracion_servicio
                         for s in stops_por_id.values()
                         if s.id in indice_parada}
    distancia, duracion = _costos_orden(matrix, coords_orden, servicio_por_nodo)

    geometria = None
    advertencias = list(resultado.advertencias or [])
    coords_geo = [matrix.coords[i] for i in coords_orden]
    try:
        geojson = proveedor.route_geometry(coords_geo, perfil)
        if validar_geometria(geojson):
            geometria = geojson
        else:
            advertencias.append('GeometrÃ­a de la ruta no superÃ³ la validaciÃ³n.')
    except MapProviderError as exc:
        advertencias.append(f'GeometrÃ­a no disponible: {exc.mensaje}')

    version = RutaVersion(
        ruta=ruta, numero=numero, tipo=tipo,
        estrategia=resultado.estrategia, version_estrategia=resultado.version,
        parametros=params.to_dict(), estado_solver=resultado.estado_solver,
        distancia_metros=distancia, duracion_seg=duracion,
        carga_total=sum(stops_por_id[s].demanda for s in asignacion),
        carga_unidad=ruta.vehiculo.unidad if ruta.vehiculo else 'kg',
        geometria_geojson=geometria, no_asignadas=no_asignadas_global,
        creado_por=usuario.id if usuario else None,
        es_vigente=False)
    db.session.add(version)
    db.session.flush()

    dist_acum = 0.0
    dur_acum = 0.0
    carga_acum = 0.0
    prev = 0
    posicion = 0
    for stop_id in asignacion:
        idx = indice_parada[stop_id]
        stop = stops_por_id[stop_id]
        dist_acum += matrix.distancias[prev][idx]
        dur_acum += matrix.duraciones[prev][idx] + stop.duracion_servicio
        carga_acum += stop.demanda
        hora = as_utc(jornada.inicio_operacion) + timedelta(seconds=dur_acum)
        solicitud = SolicitudRecoleccion.query.get(int(stop_id.split('_')[1]))
        db.session.add(ParadaRuta(
            version_id=version.id, solicitud_id=solicitud.id, posicion=posicion,
            distancia_acumulada=dist_acum, duracion_acumulada=dur_acum,
            carga_acumulada=carga_acum, hora_llegada_estimada=hora,
            estado='pendiente'))
        prev = idx
        posicion += 1
    return version


def _siguiente_numero_version(ruta):
    ultimo = db.session.query(db.func.max(RutaVersion.numero)).filter(
        RutaVersion.ruta_id == ruta.id).scalar()
    return (ultimo or 0) + 1


def optimizar_jornada(jornada_id, usuario=None, parametros=None):
    """Ejecuta lÃ­nea base + optimizaciÃ³n y persiste las versiones."""
    proveedor = get_map_provider()
    jornada = Jornada.query.get_or_404(jornada_id)
    usuario = usuario or _usuario_actual()
    params = parametros or parametros_optimizacion()

    stops, vehiculos, matrix, proveedor, perfil = construir_problema(jornada)
    stops_por_id = {s.id: s for s in stops}

    linea_base = NearestNeighborBaseline().solve(stops, vehiculos, matrix, params)
    optimizado = ORToolsVRPOptimizer().solve(stops, vehiculos, matrix, params)

    no_asignadas_global = [
        {'parada': n.parada_id, 'motivo': n.motivo}
        for n in optimizado.no_asignadas
    ]

    hash_base = hash_entrada_optimizacion(stops, vehiculos, matrix, params,
                                          matrix.proveedor, perfil)
    for resultado in (linea_base, optimizado):
        db.session.add(EjecucionOptimizacion(
            jornada_id=jornada.id, hash_entrada=hash_base,
            estrategia=resultado.estrategia, version_estrategia=resultado.version,
            parametros=resultado.parametros, estado_solver=resultado.estado_solver,
            duracion_seg=resultado.segundos, objetivo=resultado.objetivo,
            advertencias=resultado.advertencias,
            resultado=resultado_a_json(resultado)))

    asignaciones = {a.vehiculo_id: a.paradas for a in optimizado.asignaciones}
    versiones_creadas = []
    for vehiculo in jornada.vehiculos:
        if vehiculo.estado_disponibilidad != 'disponible':
            continue
        ruta = Ruta.query.filter_by(jornada_id=jornada.id,
                                    vehiculo_id=vehiculo.id).first()
        if not ruta:
            ruta = Ruta(jornada=jornada, vehiculo=vehiculo, conductor_id=None,
                        estado='borrador')
            db.session.add(ruta)
            db.session.flush()

        asignacion_base = next(
            (a.paradas for a in linea_base.asignaciones
             if a.vehiculo_id == f'veh_{vehiculo.id}'), [])
        asignacion_opt = asignaciones.get(f'veh_{vehiculo.id}', [])

        v_base = _crear_version(ruta, 'linea_base', asignacion_base, stops_por_id,
                                matrix, params, linea_base, usuario, proveedor,
                                perfil, no_asignadas_global, jornada)
        v_propuesta = _crear_version(ruta, 'propuesta', asignacion_opt,
                                     stops_por_id, matrix, params, optimizado,
                                     usuario, proveedor, perfil,
                                     no_asignadas_global, jornada)
        ruta.estado = 'propuesta'
        versiones_creadas.append({
            'ruta_id': ruta.id,
            'vehiculo': vehiculo.identificador,
            'linea_base_version_id': v_base.id,
            'propuesta_version_id': v_propuesta.id,
        })

    if not versiones_creadas:
        return {'ok': False, 'error': 'La jornada no tiene vehÃ­culos disponibles.'}

    jornada.estado = 'planificada'
    db.session.add(EventoRuta(
        ruta_id=versiones_creadas[0]['ruta_id'], actor_id=usuario.id if usuario else None,
        tipo='optimizacion', idempotencia_key=f'opt-jornada-{jornada.id}-{utcnow().timestamp()}',
        observacion='OptimizaciÃ³n de jornada ejecutada.'))

    # Se aplica la mÃ¡quina de estado de solicitudes.
    for sol in jornada.solicitudes:
        if sol.estado_operacional in ESTADOS_OPTIMIZABLES:
            sol.estado_operacional = 'asignada'

    db.session.commit()

    return {
        'ok': True,
        'jornada_id': jornada.id,
        'proveedor': matrix.proveedor,
        'perfil': perfil,
        'estimacion_vial': matrix.estimacion_vial,
        'linea_base': resultado_a_json(linea_base),
        'optimizado': resultado_a_json(optimizado),
        'versiones': versiones_creadas,
        'no_asignadas': no_asignadas_global,
    }


def _submatriz(matriz, indices):
    """Sub-matriz cuadrada con los Ã­ndices dados re-indexados desde 0."""
    coords = [matriz.coords[i] for i in indices]
    distancias = [[matriz.distancias[i][j] for j in indices] for i in indices]
    duraciones = [[matriz.duraciones[i][j] for j in indices] for i in indices]
    return MatrixData(coords=coords, duraciones=duraciones, distancias=distancias,
                      proveedor=matriz.proveedor, perfil=matriz.perfil,
                      estimacion_vial=matriz.estimacion_vial)


def recalcular_ruta(ruta_id, usuario=None, parametros=None):
    """
    Recalcula solo las paradas pendientes de una ruta.

    Las paradas completadas permanecen fijas en su secuencia; las no
    disponibles se omiten temporalmente; las pendientes se re-optimizan en
    los tramos entre paradas completadas con la capacidad restante.
    """
    proveedor = get_map_provider()
    from flask import current_app
    params = parametros or parametros_optimizacion(current_app.config)
    ruta = Ruta.query.get_or_404(ruta_id)
    jornada = ruta.jornada
    usuario = usuario or _usuario_actual()
    perfil = ruta.vehiculo.perfil_ruteo or 'driving-hgv'

    version_actual = (ruta.version_vigente
                      or RutaVersion.query.filter_by(ruta_id=ruta.id)
                      .filter(RutaVersion.tipo.in_(['propuesta', 'publicada']))
                      .order_by(RutaVersion.numero.desc()).first())
    if not version_actual:
        return {'ok': False, 'error': 'La ruta aÃºn no tiene una versiÃ³n planificada.'}

    paradas = sorted(version_actual.paradas, key=lambda p: p.posicion)
    completadas = [p for p in paradas if p.estado == 'completada']
    pendientes = [p for p in paradas if p.estado in ('pendiente', 'en_atencion')
                  and p.solicitud.estado_disponibilidad == 'disponible']
    if not pendientes:
        return {'ok': True, 'cambio': False,
                'mensaje': 'No hay paradas pendientes que recalcular.'}

    coords = [(jornada.deposito_lat, jornada.deposito_lon)]
    for p in completadas:
        coords.append((p.solicitud.punto.latitud, p.solicitud.punto.longitud))
    for p in pendientes:
        coords.append((p.solicitud.punto.latitud, p.solicitud.punto.longitud))
    matriz = proveedor.matrix(coords, perfil)
    datos_matriz = MatrixData(
        coords=matriz.coords, duraciones=matriz.duraciones,
        distancias=matriz.distancias, proveedor=matriz.proveedor,
        perfil=matriz.perfil, estimacion_vial=matriz.estimacion_vial)

    nodo_completada = [1 + i for i in range(len(completadas))]
    nodo_pendiente = {p.solicitud_id: 1 + len(completadas) + i
                      for i, p in enumerate(pendientes)}
    pos_parada = {p.solicitud_id: paradas.index(p) for p in paradas}
    pos_completadas = [pos_parada[c.solicitud_id] for c in completadas]

    tramos = []
    for i in range(len(completadas) + 1):
        inicio = 0 if i == 0 else nodo_completada[i - 1]
        fin = nodo_completada[i] if i < len(completadas) else 0
        li = -1 if i == 0 else pos_completadas[i - 1]
        lf = pos_completadas[i] if i < len(completadas) else len(paradas)
        tramos.append({
            'inicio': inicio, 'fin': fin,
            'carga_previa': sum(c.solicitud.demanda or 0 for c in completadas[:i]),
            'pendientes': [p for p in pendientes
                           if li < pos_parada[p.solicitud_id] < lf],
        })

    no_asignadas = []
    hash_partes = []
    segmentos_orden = [[] for _ in tramos]
    for k, tramo in enumerate(tramos):
        pend_tramo = tramo['pendientes']
        if not pend_tramo:
            continue
        capacidad = max((ruta.vehiculo.capacidad or 0) - tramo['carga_previa'], 0)
        nodos_tramo = ([tramo['inicio']]
                       + [nodo_pendiente[p.solicitud_id] for p in pend_tramo]
                       + [tramo['fin']])
        sub = _submatriz(datos_matriz, nodos_tramo)

        offset = _offset_segmento(jornada, version_actual, tramo, completadas)
        stops_tramo = []
        for p in pend_tramo:
            w_inicio = _segundos_desde_inicio(jornada, p.solicitud.ventana_inicio)
            w_fin = _segundos_desde_inicio(jornada, p.solicitud.ventana_fin)
            if offset:
                if w_inicio is not None:
                    w_inicio = max(0.0, w_inicio - offset)
                if w_fin is not None:
                    w_fin = max(0.0, w_fin - offset)
            stops_tramo.append(Stop(
                id=f'sol_{p.solicitud_id}',
                demanda=p.solicitud.demanda or 0,
                duracion_servicio=p.solicitud.duracion_servicio_seg or 0,
                prioridad=p.solicitud.prioridad or 3,
                ventana_inicio=w_inicio, ventana_fin=w_fin,
                lat=p.solicitud.punto.latitud, lon=p.solicitud.punto.longitud))
        vehiculo = Vehicle(id=f'veh_{ruta.vehiculo.id}', capacidad=capacidad,
                           perfil=perfil, lat_inicio=sub.coords[0][0],
                           lon_inicio=sub.coords[0][1],
                           lat_fin=sub.coords[-1][0], lon_fin=sub.coords[-1][1])
        resultado = ORToolsVRPOptimizer().solve(stops_tramo, [vehiculo],
                                                sub, params)
        hash_partes.append(hash_entrada_optimizacion(
            stops_tramo, [vehiculo], sub, params, sub.proveedor, perfil))
        for a in resultado.asignaciones:
            for stop_id in a.paradas:
                sol_id = int(stop_id.split('_')[1])
                segmentos_orden[k].append(nodo_pendiente[sol_id])
        for n in resultado.no_asignadas:
            no_asignadas.append({'parada': n.parada_id, 'motivo': n.motivo})

    orden = [0]
    for i in range(len(completadas)):
        orden.extend(segmentos_orden[i])
        orden.append(nodo_completada[i])
    orden.extend(segmentos_orden[len(completadas)])
    orden.append(0)

    servicio_por_nodo = {nodo_pendiente[p.solicitud_id]: (p.solicitud.duracion_servicio_seg or 0)
                         for p in pendientes}
    for c, nodo in zip(completadas, nodo_completada):
        servicio_por_nodo[nodo] = c.solicitud.duracion_servicio_seg or 0
    distancia, duracion = _costos_orden(datos_matriz, orden, servicio_por_nodo)

    parada_por_nodo = {}
    for c, nodo in zip(completadas, nodo_completada):
        parada_por_nodo[nodo] = c
    for p in pendientes:
        parada_por_nodo[nodo_pendiente[p.solicitud_id]] = p

    version = _crear_version_recalculo(
        ruta, datos_matriz, orden, parada_por_nodo, jornada, params,
        no_asignadas, usuario, distancia, duracion)

    db.session.add(EjecucionOptimizacion(
        ruta_id=ruta.id, hash_entrada=_hash_final(hash_partes),
        estrategia='Recalculo',
        version_estrategia=ORToolsVRPOptimizer.version,
        parametros=params.to_dict(), estado_solver='OK',
        duracion_seg=0.0, objetivo=None, advertencias=[],
        resultado={'tramos': len(tramos), 'no_asignadas': no_asignadas}))
    db.session.add(EventoRuta(
        ruta_id=ruta.id, actor_id=usuario.id if usuario else None,
        tipo='recalculo',
        idempotencia_key=f'recalc-ruta-{ruta.id}-{utcnow().timestamp()}',
        observacion='Recalculo de paradas pendientes.'))
    db.session.commit()
    return {'ok': True, 'cambio': True, 'version_id': version.id,
            'no_asignadas': no_asignadas}


def _offset_segmento(jornada, version_actual, tramo, completadas):
    """Offset de tiempo aproximado del tramo desde el inicio de la jornada."""
    if tramo['inicio'] == 0 or not completadas:
        return 0.0
    idx = tramo['inicio'] - 1
    parada = completadas[idx] if idx < len(completadas) else None
    if parada and parada.hora_llegada_estimada:
        return _segundos_desde_inicio(jornada, parada.hora_llegada_estimada) or 0.0
    return 0.0


def _crear_version_recalculo(ruta, matriz, orden, parada_por_nodo, jornada,
                             params, no_asignadas, usuario, distancia, duracion):
    version = RutaVersion(
        ruta=ruta, numero=_siguiente_numero_version(ruta), tipo='propuesta',
        estrategia=ORToolsVRPOptimizer.estrategia,
        version_estrategia=ORToolsVRPOptimizer.version,
        parametros=params.to_dict(), estado_solver='OK',
        distancia_metros=distancia, duracion_seg=duracion,
        carga_total=0.0, carga_unidad=ruta.vehiculo.unidad if ruta.vehiculo else 'kg',
        no_asignadas=no_asignadas,
        creado_por=usuario.id if usuario else None, es_vigente=False)
    db.session.add(version)
    db.session.flush()

    dist_acum = 0.0
    dur_acum = 0.0
    carga_acum = 0.0
    prev = 0
    posicion = 0
    for nodo in orden[1:-1]:
        p = parada_por_nodo.get(nodo)
        if p is None:
            continue
        sol = p.solicitud
        dist_acum += matriz.distancias[prev][nodo]
        dur_acum += matriz.duraciones[prev][nodo] + (sol.duracion_servicio_seg or 0)
        carga_acum += sol.demanda or 0
        hora = as_utc(jornada.inicio_operacion) + timedelta(seconds=dur_acum)
        db.session.add(ParadaRuta(
            version_id=version.id, solicitud_id=sol.id, posicion=posicion,
            distancia_acumulada=dist_acum, duracion_acumulada=dur_acum,
            carga_acumulada=carga_acum, hora_llegada_estimada=hora,
            estado='completada' if p.estado == 'completada' else 'pendiente'))
        prev = nodo
        posicion += 1

    version.carga_total = carga_acum
    geometria = None
    try:
        geojson = _geometria_ruta(ruta, matriz, orden)
        if validar_geometria(geojson):
            geometria = geojson
    except MapProviderError:
        geometria = None
    version.geometria_geojson = geometria
    return version


def _geometria_ruta(ruta, matriz, orden):
    proveedor = get_map_provider()
    perfil = ruta.vehiculo.perfil_ruteo or 'driving-hgv'
    coords_geo = [matriz.coords[i] for i in orden]
    return proveedor.route_geometry(coords_geo, perfil)


def _hash_final(partes):
    import hashlib
    return hashlib.sha256('|'.join(partes).encode('utf-8')).hexdigest()


def publicar_version(ruta_id, version_id, usuario=None):
    """
    Publica una versiÃ³n de ruta creando una copia inmutable.

    La propuesta original no se modifica; se crea una nueva versiÃ³n de tipo
    'publicada' que queda como vigente de la ruta y de la jornada.
    """
    ruta = Ruta.query.get_or_404(ruta_id)
    version = RutaVersion.query.get_or_404(version_id)
    if version.ruta_id != ruta.id:
        raise ValueError('La versiÃ³n no pertenece a esta ruta.')
    if version.tipo == 'publicada':
        return {'ok': True, 'version_id': version.id, 'ya_publicada': True}

    usuario = usuario or _usuario_actual()
    numero = _siguiente_numero_version(ruta)
    nueva = RutaVersion(
        ruta=ruta, numero=numero, tipo='publicada',
        estrategia=version.estrategia, version_estrategia=version.version_estrategia,
        parametros=version.parametros, estado_solver=version.estado_solver,
        distancia_metros=version.distancia_metros, duracion_seg=version.duracion_seg,
        carga_total=version.carga_total, carga_unidad=version.carga_unidad,
        geometria_geojson=version.geometria_geojson,
        no_asignadas=version.no_asignadas,
        creado_por=usuario.id if usuario else None, es_vigente=True)
    db.session.add(nueva)
    db.session.flush()

    for p in sorted(version.paradas, key=lambda p: p.posicion):
        db.session.add(ParadaRuta(
            version_id=nueva.id, solicitud_id=p.solicitud_id, posicion=p.posicion,
            distancia_acumulada=p.distancia_acumulada,
            duracion_acumulada=p.duracion_acumulada,
            carga_acumulada=p.carga_acumulada,
            hora_llegada_estimada=p.hora_llegada_estimada,
            estado=p.estado))

    for otra in ruta.versiones:
        if otra.es_vigente and otra.id != nueva.id:
            otra.es_vigente = False
    ruta.version_vigente = nueva
    ruta.estado = 'publicada'
    if ruta.jornada.estado in ('preparacion', 'planificada'):
        ruta.jornada.estado = 'publicada'
    for sol in ruta.jornada.solicitudes:
        if sol.estado_operacional in ESTADOS_OPTIMIZABLES:
            sol.estado_operacional = 'asignada'

    db.session.add(EventoRuta(
        ruta_id=ruta.id, version_id=nueva.id,
        actor_id=usuario.id if usuario else None, tipo='publicacion',
        idempotencia_key=f'publicar-ruta-{ruta.id}-{version.id}',
        observacion=f'Publicada versiÃ³n {numero} a partir de la versiÃ³n {version.id}.'))
    db.session.commit()
    return {'ok': True, 'version_id': nueva.id, 'numero': numero,
            'ya_publicada': False}


def validar_geometria(geojson):
    """Valida tamaÃ±o y formato de una geometrÃ­a LineString."""
    if not isinstance(geojson, dict) or geojson.get('type') != 'LineString':
        return False
    coords = geojson.get('coordinates')
    if not coords or len(coords) < 2:
        return False
    try:
        if len(json.dumps(geojson)) > GEOMETRIA_MAX_BYTES:
            return False
        for lon, lat in coords:
            if not (-180 <= float(lon) <= 180 and -90 <= float(lat) <= 90):
                return False
    except (TypeError, ValueError):
        return False
    return True


def geocodificar_direccion(direccion):
    proveedor = get_map_provider()
    return proveedor.geocode(direccion)


def geocodificar_reversa(lat, lon):
    proveedor = get_map_provider()
    return proveedor.reverse_geocode(lat, lon)


def obtener_estado_proveedor():
    return provider_status()


def version_a_json(version):
    """SerializaciÃ³n de una versiÃ³n para el mapa y la API."""
    paradas = []
    for p in sorted(version.paradas, key=lambda p: p.posicion):
        sol = p.solicitud
        paradas.append({
            'id': p.id, 'posicion': p.posicion, 'estado': p.estado,
            'solicitud_id': sol.id, 'numero_ticket': sol.ticket.numero if sol.ticket else None,
            'direccion': (sol.punto.direccion_normalizada
                          or sol.punto.direccion_original or ''),
            'lat': sol.punto.latitud, 'lon': sol.punto.longitud,
            'demanda': sol.demanda, 'unidad': sol.unidad_demanda,
            'hora_estimada': (as_utc(p.hora_llegada_estimada).isoformat()
                              if p.hora_llegada_estimada else None),
            'distancia_acumulada': p.distancia_acumulada,
            'duracion_acumulada': p.duracion_acumulada,
            'carga_acumulada': p.carga_acumulada,
        })
    return {
        'id': version.id, 'ruta_id': version.ruta_id, 'numero': version.numero,
        'tipo': version.tipo, 'estrategia': version.estrategia,
        'version_estrategia': version.version_estrategia,
        'estado_solver': version.estado_solver,
        'distancia_metros': version.distancia_metros,
        'duracion_seg': version.duracion_seg,
        'carga_total': version.carga_total,
        'carga_unidad': version.carga_unidad,
        'no_asignadas': version.no_asignadas or [],
        'geometria': version.geometria_geojson,
        'paradas': paradas,
        'deposito': {
            'lat': version.ruta.jornada.deposito_lat,
            'lon': version.ruta.jornada.deposito_lon,
            'direccion': version.ruta.jornada.deposito_direccion,
        },
    }
