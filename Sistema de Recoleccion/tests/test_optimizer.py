# -*- encoding: utf-8 -*-
"""Pruebas unitarias del optimizador (sin red)."""
import unittest

from apps.recoleccion.services.map_provider import FakeMapProvider
from apps.recoleccion.services.optimizer import (
    MatrixData, NearestNeighborBaseline, OptimizationParameters,
    ORToolsVRPOptimizer, Stop, Vehicle, _buscar_indice_coordenada,
    _costos_orden, resultado_a_json,
)


def _matriz_con(provider, coords):
    m = provider.matrix(coords)
    return MatrixData(coords=m.coords, duraciones=m.duraciones,
                      distancias=m.distancias, proveedor=m.proveedor,
                      perfil=m.perfil, estimacion_vial=m.estimacion_vial)


class TestFuncionesBasicas(unittest.TestCase):

    def test_buscar_indice_coordenada(self):
        provider = FakeMapProvider()
        coords = [(-33.4372, -70.6506), (-33.4800, -70.7000)]
        matriz = _matriz_con(provider, coords)
        self.assertEqual(_buscar_indice_coordenada(matriz, -33.4372, -70.6506), 0)
        self.assertEqual(_buscar_indice_coordenada(matriz, -33.4800, -70.7000), 1)
        self.assertIsNone(_buscar_indice_coordenada(matriz, 0.0, 0.0))

    def test_costos_orden(self):
        provider = FakeMapProvider()
        coords = [(-33.4372, -70.6506), (-33.4800, -70.7000), (-33.3900, -70.6100)]
        matriz = _matriz_con(provider, coords)
        dist, dur = _costos_orden(matriz, [0, 1, 2, 0], {1: 900, 2: 300})
        esperado_dist = (matriz.distancias[0][1] + matriz.distancias[1][2]
                         + matriz.distancias[2][0])
        esperado_dur = (matriz.duraciones[0][1] + matriz.duraciones[1][2]
                        + matriz.duraciones[2][0] + 900 + 300)
        self.assertEqual(dist, esperado_dist)
        self.assertEqual(dur, esperado_dur)

    def test_resultado_a_json(self):
        stops, vehs, matriz = _instancia([100])
        r = NearestNeighborBaseline().solve(stops, vehs, matriz)
        datos = resultado_a_json(r)
        for clave in ('estrategia', 'version', 'estado_solver', 'segundos',
                      'objetivo', 'duracion_total', 'distancia_total',
                      'asignaciones', 'no_asignadas', 'advertencias',
                      'parametros'):
            self.assertIn(clave, datos)

    def test_motivo_no_asignada(self):
        veh = Vehicle(id='v1', capacidad=100)
        casos = [
            (Stop(id='a', demanda=150, prioridad=3), 'capacidad'),
            (Stop(id='b', demanda=50, ventana_inicio=100, ventana_fin=50),
             'ventana_horaria_invalida'),
            (Stop(id='c', demanda=50), 'sin_coordenadas'),
            (Stop(id='d', demanda=50), 'no_asignada'),
        ]
        for stop, esperado in casos:
            kwargs = {}
            if esperado == 'no_asignada':
                kwargs['indice'] = 1
            self.assertEqual(
                ORToolsVRPOptimizer._motivo_no_asignada(stop, [veh], **kwargs),
                esperado)


def _instancia(demandas, capacidad=1000, prioridades=None):
    """Crea stops con coordenadas propias, vehículo y matriz coherentes."""
    provider = FakeMapProvider()
    coords = [(-33.4372, -70.6506)]
    stops = []
    for i, demanda in enumerate(demandas):
        lat = -33.44 - 0.01 * i
        lon = -70.65 + 0.01 * i
        coords.append((lat, lon))
        stops.append(Stop(
            id='s%d' % i, demanda=demanda, duracion_servicio=900,
            prioridad=(prioridades[i] if prioridades else 3),
            lat=lat, lon=lon))
    matriz = _matriz_con(provider, coords)
    return stops, [Vehicle(id='v1', capacidad=capacidad)], matriz


class TestNearestNeighborBaseline(unittest.TestCase):

    def test_asigna_todas_las_paradas(self):
        stops, vehs, matriz = _instancia([100, 200, 150])
        r = NearestNeighborBaseline().solve(stops, vehs, matriz)
        self.assertEqual(r.estado_solver, 'OK')
        self.assertEqual(len(r.asignaciones), 1)
        self.assertEqual(len(r.asignaciones[0].paradas), 3)
        self.assertEqual(r.no_asignadas, [])

    def test_capacidad_insuficiente(self):
        stops, vehs, matriz = _instancia([600, 600], capacidad=1000)
        r = NearestNeighborBaseline().solve(stops, vehs, matriz)
        self.assertEqual(r.estado_solver, 'INCOMPLETO')
        self.assertEqual([n.motivo for n in r.no_asignadas], ['capacidad'])

    def test_sin_vehiculos(self):
        stops, _, matriz = _instancia([100])
        r = NearestNeighborBaseline().solve(stops, [], matriz)
        self.assertEqual(r.estado_solver, 'SIN_VEHICULOS')
        self.assertEqual([n.motivo for n in r.no_asignadas], ['sin_vehiculos'])

    def test_sin_coordenadas(self):
        provider = FakeMapProvider()
        matriz = _matriz_con(provider, [(-33.4372, -70.6506)])
        stop = Stop(id='sx', demanda=10, lat=-33.99, lon=-70.99)
        r = NearestNeighborBaseline().solve(
            [stop], [Vehicle(id='v1', capacidad=100)], matriz)
        self.assertEqual([n.motivo for n in r.no_asignadas], ['sin_coordenadas'])

    def test_determinismo(self):
        stops, vehs, matriz = _instancia([120, 80, 250, 40, 300])
        a = NearestNeighborBaseline().solve(stops, vehs, matriz)
        b = NearestNeighborBaseline().solve(stops, vehs, matriz)
        self.assertEqual(a.asignaciones[0].paradas, b.asignaciones[0].paradas)
        self.assertEqual(a.objetivo, b.objetivo)
        self.assertEqual(a.distancia_total, b.distancia_total)


class TestORToolsVRP(unittest.TestCase):

    def test_soluciona_instancia_pequena(self):
        stops, vehs, matriz = _instancia([100, 200, 150, 300, 120])
        r = ORToolsVRPOptimizer().solve(stops, vehs, matriz)
        self.assertEqual(r.estado_solver, 'ROUTING_SUCCESS')
        self.assertEqual(len(r.asignaciones), 1)
        self.assertEqual(len(r.asignaciones[0].paradas), 5)
        self.assertEqual(r.no_asignadas, [])

    def test_capacidad_total_insuficiente(self):
        stops, vehs, matriz = _instancia([600, 500, 400], capacidad=1000)
        r = ORToolsVRPOptimizer().solve(stops, vehs, matriz)
        self.assertEqual(r.estado_solver, 'ROUTING_SUCCESS')
        self.assertGreater(len(r.no_asignadas), 0)
        self.assertEqual({n.motivo for n in r.no_asignadas}, {'capacidad'})

    def test_sin_vehiculos(self):
        stops, _, matriz = _instancia([100])
        r = ORToolsVRPOptimizer().solve(stops, [], matriz)
        self.assertEqual(r.estado_solver, 'SIN_VEHICULOS')

    def test_sin_paradas_pendientes(self):
        stops, vehs, matriz = _instancia([])
        r = ORToolsVRPOptimizer().solve(stops, vehs, matriz)
        self.assertEqual(r.estado_solver, 'OK')
        self.assertEqual(r.asignaciones, [])
        self.assertEqual(r.no_asignadas, [])

    def test_determinismo(self):
        stops, vehs, matriz = _instancia([120, 80, 250, 40, 300, 200])
        params = OptimizationParameters(limite_tiempo_segundos=5)
        a = ORToolsVRPOptimizer().solve(stops, vehs, matriz, params)
        b = ORToolsVRPOptimizer().solve(stops, vehs, matriz, params)
        self.assertEqual(a.objetivo, b.objetivo)
        self.assertEqual(a.asignaciones[0].paradas, b.asignaciones[0].paradas)
        self.assertEqual(a.distancia_total, b.distancia_total)

    def test_la_carga_no_excede_la_capacidad(self):
        stops, vehs, matriz = _instancia([700, 400, 300, 200], capacidad=1000)
        r = ORToolsVRPOptimizer().solve(stops, vehs, matriz)
        atendidas = sum(s.demanda for s in stops
                        if s.id in r.asignaciones[0].paradas)
        self.assertLessEqual(atendidas, 1000)


if __name__ == '__main__':
    unittest.main()
