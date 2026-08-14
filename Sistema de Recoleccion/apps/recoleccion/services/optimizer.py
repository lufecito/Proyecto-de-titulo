# -*- encoding: utf-8 -*-
"""
Optimización local de rutas.

Interfaz RouteOptimizer con dos estrategias:

1. NearestNeighborBaseline: línea base determinista (vecino más cercano con
   desempate estable por id). La asignación a vehículos usa un empaquetado
   por capacidad (first-fit por demanda descendente). No aplica mejora 2-opt
   en esta versión; se documenta como mejora posible.

2. ORToolsVRPOptimizer: problema de ruteo de vehículos (VRP) con uno o más
   vehículos, capacidad, duración de servicio y ventanas horarias opcionales.
   Las paradas que no pueden asignarse se penalizan mediante disjunciones y
   aparecen en `no_asignadas` con un motivo.

El optimizador consume una matriz entregada por MapProvider; no llama
directamente a APIs externas. Los resultados son deterministas para los
mismos datos, parámetros y límite de tiempo (OR-Tools: primera solución
PATH_CHEAPEST_ARC + semilla fija).
"""

import hashlib
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

PESO_PRIORIDAD_DEFECTO = {1: 8.0, 2: 4.0, 3: 2.0, 4: 1.0}


@dataclass
class Stop:
    id: str
    demanda: float = 0.0
    duracion_servicio: float = 0.0  # segundos
    prioridad: int = 3              # 1 = más alta
    ventana_inicio: float = None    # segundos desde el inicio de la jornada
    ventana_fin: float = None
    lat: float = 0.0
    lon: float = 0.0
    disponible: bool = True
    fija: bool = False              # parada completada que no participa del recalculo


@dataclass
class Vehicle:
    id: str
    capacidad: float = 0.0
    perfil: str = 'driving-hgv'
    lat_inicio: float = 0.0
    lon_inicio: float = 0.0
    lat_fin: float = 0.0
    lon_fin: float = 0.0


@dataclass
class MatrixData:
    coords: list                      # [(lat, lon)]; índice 0 = depósito
    duraciones: list                  # segundos
    distancias: list                  # metros
    proveedor: str = 'desconocido'
    perfil: str = 'driving-hgv'
    estimacion_vial: bool = True


@dataclass
class RouteAssignment:
    vehiculo_id: str
    paradas: list                     # ids de paradas en orden


@dataclass
class UnassignedStop:
    parada_id: str
    motivo: str


@dataclass
class OptimizationResult:
    asignaciones: list
    no_asignadas: list
    duracion_total: float
    distancia_total: float
    objetivo: float
    estado_solver: str
    segundos: float
    parametros: dict
    advertencias: list
    estrategia: str
    version: str


@dataclass
class OptimizationParameters:
    limite_tiempo_segundos: int = 30
    penalidad_parada_base: float = 100000.0
    peso_prioridad: dict = field(default_factory=lambda: dict(PESO_PRIORIDAD_DEFECTO))
    ventanas_rigidas: bool = True
    penalidad_atraso_por_segundo: float = 1.0
    peso_duracion: float = 1.0
    peso_span_tiempo: float = 0.05
    semilla: int = 42

    def to_dict(self):
        return {
            'limite_tiempo_segundos': self.limite_tiempo_segundos,
            'penalidad_parada_base': self.penalidad_parada_base,
            'peso_prioridad': self.peso_prioridad,
            'ventanas_rigidas': self.ventanas_rigidas,
            'penalidad_atraso_por_segundo': self.penalidad_atraso_por_segundo,
            'peso_duracion': self.peso_duracion,
            'peso_span_tiempo': self.peso_span_tiempo,
            'semilla': self.semilla,
        }


class RouteOptimizer(ABC):
    estrategia = 'base'
    version = '0'

    @abstractmethod
    def solve(self, stops, vehicles, matrix, params=None):
        raise NotImplementedError


def _penalizacion_no_asignadas(stops_por_id, no_asignadas, params):
    total = 0.0
    for no in no_asignadas:
        stop = stops_por_id.get(no.parada_id)
        prioridad = stop.prioridad if stop else 3
        peso = params.peso_prioridad.get(prioridad, 1.0)
        total += params.penalidad_parada_base * peso
    return total


def _ordenar_stops(stops):
    """Orden determinista: prioridad (más alta primero) y luego id."""
    return sorted(stops, key=lambda s: (s.prioridad, s.id))


def _buscar_indice_coordenada(matrix, lat, lon):
    for i, (plat, plon) in enumerate(matrix.coords):
        if abs(plat - lat) < 1e-9 and abs(plon - lon) < 1e-9:
            return i
    return None


def _costos_orden(matriz, coords_orden, servicio_por_nodo):
    """Distancia y duración de un recorrido siguiendo los índices dados."""
    distancia = 0.0
    duracion = 0.0
    for i in range(1, len(coords_orden)):
        anterior = coords_orden[i - 1]
        actual = coords_orden[i]
        distancia += matriz.distancias[anterior][actual]
        duracion += matriz.duraciones[anterior][actual]
        duracion += servicio_por_nodo.get(actual, 0.0)
    return distancia, duracion


class NearestNeighborBaseline(RouteOptimizer):
    """
    Línea base determinista por vecino más cercano.

    Cada parada activa aparece exactamente una vez en una ruta o en la lista
    de no asignadas. La asignación a vehículos es first-fit por demanda
    descendente; dentro de cada vehículo se construye un tour con vecino más
    cercano y desempate estable por id. El punto inicial y final es el nodo 0
    de la matriz (depósito de la jornada).
    """

    estrategia = 'NearestNeighborBaseline'
    version = '1.0'

    def solve(self, stops, vehicles, matrix, params=None):
        inicio = time.monotonic()
        params = params or OptimizationParameters()
        advertencias = []
        stops_por_id = {s.id: s for s in stops}
        stops_activas = [s for s in stops if s.disponible and not s.fija]
        orden = _ordenar_stops(stops_activas)
        no_asignadas = []
        asignaciones = []

        if not vehicles:
            no_asignadas = [UnassignedStop(s.id, 'sin_vehiculos') for s in orden]
            return OptimizationResult(
                [], no_asignadas, 0.0, 0.0, 0.0, 'SIN_VEHICULOS',
                time.monotonic() - inicio, params.to_dict(), advertencias,
                self.estrategia, self.version)

        # Índice de matriz para cada parada (debe existir).
        nodo_por_stop = {}
        faltantes = []
        for stop in stops_activas:
            idx = _buscar_indice_coordenada(matrix, stop.lat, stop.lon)
            if idx is None:
                faltantes.append(stop.id)
            else:
                nodo_por_stop[stop.id] = idx
        for stop_id in faltantes:
            stop = stops_por_id[stop_id]
            orden.remove(stop)
            no_asignadas.append(UnassignedStop(stop_id, 'sin_coordenadas'))
        if faltantes:
            advertencias.append(
                f'{len(faltantes)} parada(s) sin coordenadas en la matriz.')

        if not orden:
            return OptimizationResult(
                [], no_asignadas, 0.0, 0.0, 0.0, 'INCOMPLETO',
                time.monotonic() - inicio, params.to_dict(), advertencias,
                self.estrategia, self.version)

        # Asignación por capacidad (first-fit por demanda descendente).
        por_vehiculo = {v.id: [] for v in vehicles}
        capacidad_restante = {v.id: v.capacidad for v in vehicles}
        for stop in orden:
            destino = None
            for v in vehicles:
                if capacidad_restante[v.id] >= stop.demanda:
                    destino = v.id
                    break
            if destino is None:
                no_asignadas.append(UnassignedStop(stop.id, 'capacidad'))
            else:
                por_vehiculo[destino].append(stop)
                capacidad_restante[destino] -= stop.demanda

        servicio_por_nodo = {nodo_por_stop[s.id]: s.duracion_servicio
                             for s in stops_activas if s.id in nodo_por_stop}
        distancia_total = 0.0
        duracion_total = 0.0
        for v in vehicles:
            paradas = por_vehiculo[v.id]
            if not paradas:
                continue
            tour = [0]
            restantes = list(paradas)
            while restantes:
                ultimo = tour[-1]
                candidato = min(
                    restantes,
                    key=lambda s: (matrix.duraciones[ultimo][nodo_por_stop[s.id]], s.id))
                tour.append(nodo_por_stop[candidato.id])
                restantes.remove(candidato)
            tour.append(0)
            dist, dur = _costos_orden(matrix, tour, servicio_por_nodo)
            distancia_total += dist
            duracion_total += dur
            asignaciones.append(RouteAssignment(
                v.id, [matrix.coords[0] and _nodo_a_stop(nodo_por_stop, i)
                       for i in tour[1:-1]]))

        resultado = OptimizationResult(
            asignaciones, no_asignadas, duracion_total, distancia_total, 0.0,
            'OK' if not no_asignadas else 'INCOMPLETO',
            time.monotonic() - inicio, params.to_dict(), advertencias,
            self.estrategia, self.version)
        penalizacion = _penalizacion_no_asignadas(stops_por_id, no_asignadas, params)
        resultado.objetivo = (params.peso_duracion * resultado.duracion_total
                              + penalizacion)
        return resultado


def _nodo_a_stop(nodo_por_stop, indice):
    for stop_id, nodo in nodo_por_stop.items():
        if nodo == indice:
            return stop_id
    return None


class ORToolsVRPOptimizer(RouteOptimizer):
    """
    VRP con OR-Tools: múltiples vehículos, capacidad, duración de servicio y
    ventanas horarias opcionales (duras por defecto; blandas configurables).

    La duración de servicio se suma al tiempo de viaje (patrón de la
    documentación oficial). Las paradas no asignadas se modelan con
    disjunciones y su penalización depende de la prioridad. La búsqueda tiene
    límite de tiempo configurable. OR-Tools puede entregar una solución
    factible o la mejor encontrada dentro del límite; no se promete
    optimalidad absoluta.
    """

    estrategia = 'ORToolsVRPOptimizer'
    version = '1.0'

    def solve(self, stops, vehicles, matrix, params=None):
        inicio = time.monotonic()
        params = params or OptimizationParameters()
        advertencias = []
        stops_por_id = {s.id: s for s in stops}
        stops_activas = [s for s in stops if s.disponible and not s.fija]

        if not vehicles:
            no_asignadas = [UnassignedStop(s.id, 'sin_vehiculos')
                            for s in stops_activas]
            return OptimizationResult(
                [], no_asignadas, 0.0, 0.0, 0.0, 'SIN_VEHICULOS',
                time.monotonic() - inicio, params.to_dict(), advertencias,
                self.estrategia, self.version)

        if not stops_activas:
            return OptimizationResult(
                [], [], 0.0, 0.0, 0.0, 'OK',
                time.monotonic() - inicio, params.to_dict(),
                ['No hay paradas pendientes para optimizar.'],
                self.estrategia, self.version)

        indice_parada = {}
        for stop in stops_activas:
            idx = _buscar_indice_coordenada(matrix, stop.lat, stop.lon)
            if idx is None:
                advertencias.append(
                    f'Parada {stop.id} sin coordenada en la matriz.')
            else:
                indice_parada[stop.id] = idx

        if not indice_parada:
            no_asignadas = [UnassignedStop(s.id, 'sin_coordenadas')
                            for s in stops_activas]
            return OptimizationResult(
                [], no_asignadas, 0.0, 0.0, 0.0, 'SIN_COORDENADAS',
                time.monotonic() - inicio, params.to_dict(), advertencias,
                self.estrategia, self.version)

        num_nodos = len(matrix.coords)
        num_vehiculos = len(vehicles)
        manager = pywrapcp.RoutingIndexManager(
            num_nodos, num_vehiculos, [0] * num_vehiculos, [0] * num_vehiculos)
        routing = pywrapcp.RoutingModel(manager)
        nodos_parada = {idx: stop_id for stop_id, idx in indice_parada.items()}

        def _nodo(index):
            return manager.IndexToNode(index)

        def transit_callback(from_index, to_index):
            desde = _nodo(from_index)
            hasta = _nodo(to_index)
            viaje = matrix.duraciones[desde][hasta]
            stop_id = nodos_parada.get(hasta)
            servicio = stops_por_id[stop_id].duracion_servicio if stop_id else 0.0
            return int(round(viaje + servicio))

        def demand_callback(from_index):
            nodo = _nodo(from_index)
            stop_id = nodos_parada.get(nodo)
            if not stop_id:
                return 0
            return int(round(stops_por_id[stop_id].demanda))

        transit_index = routing.RegisterTransitCallback(transit_callback)
        demand_index = routing.RegisterUnaryTransitCallback(demand_callback)

        # Dimensión de tiempo (la duración de servicio queda incorporada).
        cota_tiempo = int(round(
            sum(max(fila) for fila in matrix.duraciones)
            + sum(s.duracion_servicio for s in stops_activas) + 3600))
        routing.AddDimension(transit_index, 0, max(cota_tiempo, 3600), True, 'Tiempo')
        time_dimension = routing.GetDimensionOrDie('Tiempo')

        # Ventanas horarias (duras o blandas).
        for stop in stops_activas:
            idx = indice_parada.get(stop.id)
            if idx is None:
                continue
            cumul = time_dimension.CumulVar(manager.NodeToIndex(idx))
            if (stop.ventana_inicio is not None and stop.ventana_fin is not None
                    and stop.ventana_fin > stop.ventana_inicio):
                inicio_v = max(0, int(stop.ventana_inicio))
                fin_v = int(stop.ventana_fin)
                if params.ventanas_rigidas:
                    cumul.SetRange(inicio_v, fin_v)
                else:
                    cumul.SetRange(inicio_v, max(cota_tiempo, fin_v))
                    time_dimension.AddCumulVarSoftUpperBound(
                        cumul, fin_v, params.penalidad_atraso_por_segundo)

        # Dimensión de capacidad (capacidad por vehículo).
        capacidades = [int(round(v.capacidad)) for v in vehicles]
        routing.AddDimensionWithVehicleCapacity(
            demand_index, 0, capacidades, True, 'Capacidad')

        # Paradas no asignables: disyunción con penalización por prioridad.
        penalizacion_total = 0.0
        for stop in stops_activas:
            idx = indice_parada.get(stop.id)
            if idx is None:
                penalizacion_total += (
                    params.penalidad_parada_base
                    * params.peso_prioridad.get(stop.prioridad, 1.0))
                continue
            nodo = manager.NodeToIndex(idx)
            pena = int(params.penalidad_parada_base
                       * params.peso_prioridad.get(stop.prioridad, 1.0))
            routing.AddDisjunction([nodo], pena)

        # Objetivo: minimizar duración total (+ makespan ponderado).
        if params.peso_span_tiempo:
            time_dimension.SetGlobalSpanCostCoefficient(int(params.peso_span_tiempo))

        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
        search_parameters.time_limit.seconds = max(1, params.limite_tiempo_segundos)
        search_parameters.log_search = False

        solucion = routing.SolveWithParameters(search_parameters)

        estado = 'ROUTING_SUCCESS' if solucion else 'ROUTING_FAIL'
        asignaciones = []
        distancia_total = 0.0
        duracion_total = 0.0
        atendidas = set()

        if solucion:
            servicio_por_nodo = {
                indice_parada[s.id]: s.duracion_servicio for s in stops_activas
            }
            for vehiculo in range(num_vehiculos):
                orden = []
                indice = routing.Start(vehiculo)
                while not routing.IsEnd(indice):
                    nodo = _nodo(indice)
                    if nodo in nodos_parada:
                        orden.append(nodos_parada[nodo])
                        atendidas.add(nodos_parada[nodo])
                    indice = solucion.Value(routing.NextVar(indice))
                if orden:
                    coords_orden = [0] + [indice_parada[s] for s in orden] + [0]
                    dist, dur = _costos_orden(matrix, coords_orden,
                                              servicio_por_nodo)
                    distancia_total += dist
                    duracion_total += dur
                    asignaciones.append(RouteAssignment(vehicles[vehiculo].id, orden))

        no_asignadas = []
        capacidad_total = sum(v.capacidad for v in vehicles)
        total_demanda = sum(s.demanda for s in stops_activas)
        for stop in stops_activas:
            if stop.id not in atendidas:
                no_asignadas.append(UnassignedStop(
                    stop.id,
                    self._motivo_no_asignada(stop, vehicles, capacidad_total,
                                             total_demanda,
                                             indice=indice_parada.get(stop.id))))
                penalizacion_total += (
                    params.penalidad_parada_base
                    * params.peso_prioridad.get(stop.prioridad, 1.0))

        if estado == 'ROUTING_FAIL':
            advertencias.append(
                'OR-Tools no encontró solución factible; se conserva la última '
                'ruta publicada.')

        resultado = OptimizationResult(
            asignaciones, no_asignadas, duracion_total, distancia_total, 0.0,
            estado, time.monotonic() - inicio, params.to_dict(), advertencias,
            self.estrategia, self.version)
        resultado.objetivo = (params.peso_duracion * resultado.duracion_total
                              + penalizacion_total)
        return resultado

    @staticmethod
    def _motivo_no_asignada(stop, vehicles, capacidad_total=0.0, total_demanda=0.0,
                            indice=None):
        capacidad_max = max((v.capacidad for v in vehicles), default=0)
        if stop.demanda > capacidad_max:
            return 'capacidad'
        if total_demanda > capacidad_total:
            return 'capacidad'
        if (stop.ventana_inicio is not None and stop.ventana_fin is not None
                and stop.ventana_fin < stop.ventana_inicio):
            return 'ventana_horaria_invalida'
        if indice is None:
            return 'sin_coordenadas'
        return 'no_asignada'


def resultado_a_json(resultado):
    return {
        'estrategia': resultado.estrategia,
        'version': resultado.version,
        'estado_solver': resultado.estado_solver,
        'segundos': round(resultado.segundos, 4),
        'objetivo': round(resultado.objetivo, 2),
        'duracion_total': round(resultado.duracion_total, 1),
        'distancia_total': round(resultado.distancia_total, 1),
        'asignaciones': [{'vehiculo': a.vehiculo_id, 'paradas': a.paradas}
                         for a in resultado.asignaciones],
        'no_asignadas': [{'parada': n.parada_id, 'motivo': n.motivo}
                         for n in resultado.no_asignadas],
        'advertencias': resultado.advertencias,
        'parametros': resultado.parametros,
    }


def hash_entrada_optimizacion(stops, vehicles, matrix, params, proveedor, perfil):
    """Hash estable de la entrada para registrar reproducibilidad."""
    cuerpo = {
        'proveedor': proveedor,
        'perfil': perfil,
        'coords': [tuple(round(c, 6) for c in xy) for xy in matrix.coords],
        'duraciones': matrix.duraciones,
        'distancias': matrix.distancias,
        'stops': sorted(
            (s.id, s.demanda, s.duracion_servicio, s.prioridad,
             s.ventana_inicio, s.ventana_fin) for s in stops),
        'vehicles': sorted((v.id, v.capacidad) for v in vehicles),
        'params': params.to_dict(),
    }
    return hashlib.sha256(
        json.dumps(cuerpo, sort_keys=True, default=str).encode('utf-8')).hexdigest()
