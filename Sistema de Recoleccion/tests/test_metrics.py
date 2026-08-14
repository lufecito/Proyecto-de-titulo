# -*- encoding: utf-8 -*-
"""Pruebas de métricas de planificación."""
import unittest

from apps import db
from base_recoleccion import RecoleccionTestCase


class TestMetricas(RecoleccionTestCase):

    def test_metricas_antes_de_optimizar(self):
        from apps.recoleccion.services.metrics import metricas_jornada
        m = metricas_jornada(self.jornada)
        self.assertEqual(m['jornada_id'], self.jornada.id)
        self.assertEqual(m['cantidad_rutas'], 0)
        self.assertIsNone(m['distancia_base_total_m'])
        self.assertEqual(m['cantidad_no_asignadas'], 0)
        self.assertEqual(m['optimizaciones'], 0)

    def test_metricas_despues_de_optimizar_y_publicar(self):
        from apps.recoleccion.services.metrics import metricas_jornada, metricas_ruta
        ruta = self.planificar_y_publicar()
        m = metricas_jornada(self.jornada)
        self.assertEqual(m['cantidad_rutas'], 1)
        self.assertIsNotNone(m['distancia_base_total_m'])
        self.assertIsNotNone(m['distancia_propuesta_total_m'])
        self.assertEqual(m['cantidad_no_asignadas'], 3)
        self.assertGreater(m['optimizaciones'], 0)
        self.assertEqual(m['publicaciones'], 1)

        mr = metricas_ruta(ruta)
        self.assertEqual(mr['ruta_id'], ruta.id)
        self.assertEqual(mr['vehiculo'], 'CAM-01')
        self.assertEqual(mr['distancia_publicada_m'], mr['distancia_propuesta_m'])
        self.assertIsNotNone(mr['utilizacion_pct'])
        self.assertLessEqual(mr['utilizacion_pct'], 100)

    def test_metricas_recalculo(self):
        ruta = self.planificar_y_publicar()
        completada = ruta.version_vigente.paradas[0]
        completada.estado = 'completada'
        completada.solicitud.estado_operacional = 'completada'
        db.session.commit()
        from apps.recoleccion.services.planning import recalcular_ruta
        recalcular_ruta(ruta.id)
        from apps.recoleccion.services.metrics import metricas_jornada
        m = metricas_jornada(self.jornada)
        self.assertGreaterEqual(m['recalculos'], 1)


if __name__ == '__main__':
    unittest.main()
