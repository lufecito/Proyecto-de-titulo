# -*- encoding: utf-8 -*-
"""Pruebas de los servicios de planificación (sin red, proveedor fake)."""
import unittest

from apps import db
from base_recoleccion import RecoleccionTestCase


class TestConstruccionYGeocodificacion(RecoleccionTestCase):

    def test_construir_problema(self):
        from apps.recoleccion.services.planning import construir_problema
        stops, vehiculos, matriz, proveedor, perfil = construir_problema(self.jornada)
        self.assertEqual(matriz.coords[0], (self.jornada.deposito_lat,
                                            self.jornada.deposito_lon))
        self.assertEqual(len(stops), 8)
        self.assertEqual(len(vehiculos), 1)
        self.assertEqual({s.id for s in stops},
                         {'sol_%d' % sol.id for sol in self.jornada.solicitudes})
        self.assertEqual(vehiculos[0].capacidad, 1000)

    def test_geocodificar_direccion_sin_red(self):
        from apps.recoleccion.services.planning import geocodificar_direccion
        r = geocodificar_direccion('Av. Pajaritos 2100, Maipú')
        self.assertEqual(r.proveedor, 'fake')
        self.assertTrue(-34.0 <= r.lat <= -33.0)
        self.assertTrue(-71.0 <= r.lon <= -70.0)

    def test_validar_geometria(self):
        from apps.recoleccion.services.planning import validar_geometria
        valida = {'type': 'LineString', 'coordinates': [[-70.65, -33.43], [-70.60, -33.40]]}
        self.assertTrue(validar_geometria(valida))
        self.assertFalse(validar_geometria({'type': 'Point', 'coordinates': [1, 2]}))
        self.assertFalse(validar_geometria({'type': 'LineString', 'coordinates': [[-70.65, -33.43]]}))
        self.assertFalse(validar_geometria({'type': 'LineString',
                                            'coordinates': [[200, 91], [-70.6, -33.4]]}))
        self.assertFalse(validar_geometria(None))
        self.assertFalse(validar_geometria('no es geometría'))


class TestOptimizacionJornada(RecoleccionTestCase):

    def test_optimizar_jornada_persiste_versiones(self):
        from apps.recoleccion.services.planning import optimizar_jornada
        resumen = optimizar_jornada(self.jornada.id)
        self.assertTrue(resumen['ok'])
        self.assertEqual(resumen['proveedor'], 'fake')
        self.assertFalse(resumen['estimacion_vial'])
        self.assertEqual(resumen['optimizado']['estado_solver'], 'ROUTING_SUCCESS')
        self.assertEqual(len(resumen['versiones']), 1)
        self.assertEqual(len(resumen['no_asignadas']), 3)
        self.assertEqual({n['motivo'] for n in resumen['no_asignadas']}, {'capacidad'})

        ruta = self.jornada.rutas[0]
        tipos = {v.tipo for v in ruta.versiones}
        self.assertEqual(tipos, {'linea_base', 'propuesta'})
        propuesta = next(v for v in ruta.versiones if v.tipo == 'propuesta')
        self.assertLessEqual(propuesta.carga_total, 1000)
        self.assertEqual(propuesta.carga_unidad, 'kg')
        self.assertGreater(propuesta.distancia_metros, 0)
        self.assertEqual(ruta.estado, 'propuesta')

    def test_linea_base_y_propuesta_registradas(self):
        from apps.recoleccion.models import EjecucionOptimizacion
        from apps.recoleccion.services.planning import optimizar_jornada
        optimizar_jornada(self.jornada.id)
        ejecuciones = EjecucionOptimizacion.query.filter_by(
            jornada_id=self.jornada.id).all()
        self.assertEqual(len(ejecuciones), 2)
        estrategias = {e.estrategia for e in ejecuciones}
        self.assertIn('NearestNeighborBaseline', estrategias)
        self.assertIn('ORToolsVRPOptimizer', estrategias)


class TestPublicacion(RecoleccionTestCase):

    def test_publicar_crea_copia_inmutable_vigente(self):
        ruta = self.planificar_y_publicar()
        publicada = ruta.version_vigente
        self.assertEqual(publicada.tipo, 'publicada')
        self.assertTrue(publicada.es_vigente)
        self.assertEqual(ruta.estado, 'publicada')
        self.assertEqual(self.jornada.estado, 'publicada')

        propuesta = next(v for v in ruta.versiones if v.tipo == 'propuesta')
        self.assertFalse(propuesta.es_vigente)
        self.assertEqual([p.solicitud_id for p in propuesta.paradas],
                         [p.solicitud_id for p in publicada.paradas])
        self.assertEqual(propuesta.distancia_metros, publicada.distancia_metros)
        self.assertEqual(propuesta.geometria_geojson, publicada.geometria_geojson)

        # la publicada no está enlazada como paradas a la propuesta
        self.assertIsNot(publicada, propuesta)

    def test_publicar_idempotente(self):
        from apps.recoleccion.services.planning import publicar_version
        ruta = self.planificar_y_publicar()
        publicada = ruta.version_vigente
        r = publicar_version(ruta.id, publicada.id)
        self.assertTrue(r['ok'])
        self.assertTrue(r['ya_publicada'])
        pubs = [v for v in ruta.versiones if v.tipo == 'publicada']
        self.assertEqual(len(pubs), 1)

    def test_publicar_version_de_otra_ruta_rechazada(self):
        from apps.recoleccion.models import Ruta, Vehiculo
        from apps.recoleccion.services.planning import (optimizar_jornada,
                                                        publicar_version)
        optimizar_jornada(self.jornada.id)
        otra = Vehiculo(identificador='CAM-02', nombre='Camión 02',
                        capacidad=800, unidad='kg', estado_disponibilidad='disponible',
                        perfil_ruteo='driving-hgv', lat_inicio=-33.4, lon_inicio=-70.6,
                        lat_fin=-33.4, lon_fin=-70.6)
        db.session.add(otra)
        db.session.flush()
        otra_ruta = Ruta(jornada_id=self.jornada.id, vehiculo_id=otra.id,
                         estado='borrador')
        db.session.add(otra_ruta)
        db.session.flush()
        ruta = self.jornada.rutas[0]
        version = next(v for v in ruta.versiones if v.tipo == 'propuesta')
        with self.assertRaises(ValueError):
            publicar_version(otra_ruta.id, version.id)


class TestRecalculo(RecoleccionTestCase):

    def test_recalcular_conserva_paradas_completadas(self):
        ruta = self.planificar_y_publicar()
        vigente = ruta.version_vigente
        completada = vigente.paradas[0]
        completada.estado = 'completada'
        completada.solicitud.estado_operacional = 'completada'
        db.session.commit()

        from apps.recoleccion.services.planning import recalcular_ruta
        r = recalcular_ruta(ruta.id)
        self.assertTrue(r['ok'])
        self.assertTrue(r['cambio'])
        self.assertIn('version_id', r)

        propuesta = next(v for v in ruta.versiones
                         if v.id == r['version_id'])
        self.assertEqual(propuesta.tipo, 'propuesta')
        self.assertEqual(propuesta.paradas[0].solicitud_id,
                         completada.solicitud_id)
        self.assertEqual(propuesta.paradas[0].estado, 'completada')
        pendientes = [p for p in propuesta.paradas if p.estado != 'completada']
        self.assertNotIn(completada.solicitud_id,
                         [p.solicitud_id for p in pendientes])

    def test_recalcular_sin_pendientes(self):
        ruta = self.planificar_y_publicar()
        vigente = ruta.version_vigente
        for p in vigente.paradas:
            p.estado = 'completada'
            p.solicitud.estado_operacional = 'completada'
        db.session.commit()
        from apps.recoleccion.services.planning import recalcular_ruta
        r = recalcular_ruta(ruta.id)
        self.assertTrue(r['ok'])
        self.assertFalse(r['cambio'])

    def test_recalcular_sin_version_planificada(self):
        from apps.recoleccion.models import Ruta
        from apps.recoleccion.services.planning import recalcular_ruta
        ruta = Ruta(jornada_id=self.jornada.id,
                    vehiculo_id=self.jornada.vehiculos[0].id,
                    estado='borrador')
        db.session.add(ruta)
        db.session.commit()
        r = recalcular_ruta(ruta.id)
        self.assertFalse(r['ok'])


class TestVersionAJSON(RecoleccionTestCase):

    def test_version_a_json(self):
        from apps.recoleccion.services.planning import version_a_json
        ruta = self.planificar_y_publicar()
        datos = version_a_json(ruta.version_vigente)
        for clave in ('id', 'ruta_id', 'numero', 'tipo', 'estrategia',
                      'estado_solver', 'distancia_metros', 'duracion_seg',
                      'carga_total', 'carga_unidad', 'no_asignadas',
                      'geometria', 'paradas', 'deposito'):
            self.assertIn(clave, datos)
        self.assertEqual(datos['tipo'], 'publicada')
        self.assertGreater(len(datos['paradas']), 0)
        posiciones = [p['posicion'] for p in datos['paradas']]
        self.assertEqual(posiciones, sorted(posiciones))
        self.assertIsNotNone(datos['geometria'])
        self.assertEqual(datos['deposito']['lat'], self.jornada.deposito_lat)


if __name__ == '__main__':
    unittest.main()
