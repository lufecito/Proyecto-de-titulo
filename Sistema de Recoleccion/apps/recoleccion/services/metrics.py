# -*- encoding: utf-8 -*-
"""
Métricas de planificación y ejecución.

Todas las distancias y duraciones provienen de la matriz de viaje y se
presentan como estimaciones (el proveedor cartográfico las etiqueta como tal
cuando es una aproximación, p. ej. en modo demo).
"""

from apps.recoleccion.models import EjecucionOptimizacion, RutaVersion


def _redondear(valor, digitos=2):
    if valor is None:
        return None
    return round(float(valor), digitos)


def _diferencia(base, propuesta):
    if base is None or propuesta is None or base == 0:
        return None
    return _redondear(((propuesta - base) / base) * 100)


def metricas_ruta(ruta):
    """Métricas de la última línea base, propuesta y publicación de la ruta."""
    versiones = (RutaVersion.query.filter_by(ruta_id=ruta.id)
                 .order_by(RutaVersion.numero.desc()).all())
    base = next((v for v in versiones if v.tipo == 'linea_base'), None)
    propuesta = next((v for v in versiones if v.tipo == 'propuesta'), None)
    publicada = next((v for v in versiones if v.tipo == 'publicada'), None)

    distancia_base = base.distancia_metros if base else None
    duracion_base = base.duracion_seg if base else None
    distancia_prop = propuesta.distancia_metros if propuesta else None
    duracion_prop = propuesta.duracion_seg if propuesta else None
    distancia_pub = publicada.distancia_metros if publicada else None
    duracion_pub = publicada.duracion_seg if publicada else None

    no_asignadas = (propuesta.no_asignadas if propuesta else []) or []
    capacidad = ruta.vehiculo.capacidad if ruta.vehiculo else None
    carga = propuesta.carga_total if propuesta else 0
    utilizacion = None
    if capacidad and carga:
        utilizacion = _redondear((carga / capacidad) * 100)

    ejecuciones = EjecucionOptimizacion.query.filter_by(ruta_id=ruta.id).all()
    tiempo_solver = sum(e.duracion_seg or 0 for e in ejecuciones) or None

    return {
        'ruta_id': ruta.id,
        'vehiculo': ruta.vehiculo.identificador if ruta.vehiculo else None,
        'distancia_base_m': distancia_base,
        'duracion_base_s': duracion_base,
        'distancia_propuesta_m': distancia_prop,
        'duracion_propuesta_s': duracion_prop,
        'distancia_publicada_m': distancia_pub,
        'duracion_publicada_s': duracion_pub,
        'diff_distancia_abs': (_redondear(distancia_prop - distancia_base)
                               if distancia_base is not None and distancia_prop is not None
                               else None),
        'diff_duracion_abs': (_redondear(duracion_prop - duracion_base)
                              if duracion_base is not None and duracion_prop is not None
                              else None),
        'diff_distancia_pct': _diferencia(distancia_base, distancia_prop),
        'diff_duracion_pct': _diferencia(duracion_base, duracion_prop),
        'no_asignadas': no_asignadas,
        'cantidad_no_asignadas': len(no_asignadas),
        'carga_total': carga,
        'capacidad': capacidad,
        'utilizacion_pct': utilizacion,
        'tiempo_solver_s': tiempo_solver,
        'recalculos': sum(1 for e in ejecuciones if e.estrategia == 'Recalculo'),
        'publicaciones': sum(1 for v in versiones if v.tipo == 'publicada'),
        'estimacion_vial': not (getattr(ruta.jornada, '_demo_proveedor', False)),
    }


def metricas_jornada(jornada):
    """Agrega las métricas de las rutas de la jornada."""
    resultados = [metricas_ruta(r) for r in jornada.rutas]
    ejecuciones = EjecucionOptimizacion.query.filter_by(jornada_id=jornada.id).all()

    tiempo_solver = sum(e.duracion_seg or 0 for e in ejecuciones) or None
    no_asignadas = [n for m in resultados for n in m['no_asignadas']]
    optimizaciones = sum(1 for e in ejecuciones
                         if e.estrategia.startswith('ORTools'))
    base_total = sum(m['distancia_base_m'] or 0 for m in resultados)
    prop_total = sum(m['distancia_propuesta_m'] or 0 for m in resultados)
    dur_base_total = sum(m['duracion_base_s'] or 0 for m in resultados)
    dur_prop_total = sum(m['duracion_propuesta_s'] or 0 for m in resultados)

    return {
        'jornada_id': jornada.id,
        'cantidad_rutas': len(resultados),
        'rutas': resultados,
        'distancia_base_total_m': base_total or None,
        'duracion_base_total_s': dur_base_total or None,
        'distancia_propuesta_total_m': prop_total or None,
        'duracion_propuesta_total_s': dur_prop_total or None,
        'diff_distancia_pct': _diferencia(base_total or None, prop_total),
        'diff_duracion_pct': _diferencia(dur_base_total or None, dur_prop_total),
        'no_asignadas': no_asignadas,
        'cantidad_no_asignadas': len(no_asignadas),
        'tiempo_solver_s': tiempo_solver,
        'optimizaciones': optimizaciones,
        'recalculos': sum(m['recalculos'] for m in resultados),
        'publicaciones': sum(m['publicaciones'] for m in resultados),
    }
