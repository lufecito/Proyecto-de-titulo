# -*- encoding: utf-8 -*-
"""Pruebas HTTP: autorización por rol, CSRF y API JSON."""
import unittest

from apps import db
from base_recoleccion import RecoleccionTestCase


class TestAutorizacion(RecoleccionTestCase):

    def test_anonimo_redirige_a_login(self):
        r = self.client.get('/recoleccion')
        self.assertIn(r.status_code, (301, 302))
        self.assertIn('/login', r.headers.get('Location', ''))

    def test_conductor_bloqueado_en_vistas_despachador(self):
        self.login('demo-conductor')
        for url in ('/recoleccion/solicitudes', '/recoleccion/vehiculos',
                    '/recoleccion/jornadas', '/recoleccion/jornadas/1',
                    '/recoleccion/planificacion?jornada_id=1',
                    '/recoleccion/historial'):
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_despachador_accede_a_vistas(self):
        self.login('demo-despachador')
        for url in ('/recoleccion', '/recoleccion/solicitudes',
                    '/recoleccion/vehiculos', '/recoleccion/jornadas',
                    '/recoleccion/historial', '/recoleccion/mi-ruta'):
            self.assertEqual(self.client.get(url).status_code, 200)

    def test_conductor_ve_su_seccion(self):
        self.login('demo-conductor')
        self.assertEqual(self.client.get('/recoleccion/mi-ruta').status_code, 200)
        self.assertEqual(self.client.get('/recoleccion').status_code, 200)


class TestCSRF(RecoleccionTestCase):

    def test_api_sin_csrf_rechazada(self):
        self.login('demo-despachador')
        r = self.client.post('/api/v1/recoleccion/geocodificar',
                             json={'direccion': 'Av. Pajaritos 2100'})
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.get_json()['ok'])

    def test_api_csrf_invalido_rechazada(self):
        self.login('demo-despachador')
        r = self.client.post('/api/v1/recoleccion/geocodificar',
                             json={'direccion': 'Av. Pajaritos 2100'},
                             headers={'X-CSRFToken': 'token-invalido'})
        self.assertEqual(r.status_code, 400)

    def test_formulario_con_su_propio_token_no_bloqueado(self):
        """Los formularios FlaskForm validan su propio token (se omite el guard)."""
        self.login('demo-despachador')
        html = self.client.get('/recoleccion/vehiculos/nuevo').data.decode('utf-8')
        self.assertIn('name="csrf_token"', html)


class TestApiGeocodificacion(RecoleccionTestCase):

    def test_geocodificar_ok(self):
        self.login('demo-despachador')
        token = self.csrf_token()
        r = self.client.post('/api/v1/recoleccion/geocodificar',
                             json={'direccion': 'Av. Pajaritos 2100, Maipú'},
                             headers={'X-CSRFToken': token})
        self.assertEqual(r.status_code, 200)
        datos = r.get_json()
        self.assertTrue(datos['ok'])
        self.assertEqual(datos['proveedor'], 'fake')
        self.assertIn('lat', datos)

    def test_geocodificar_direccion_vacia(self):
        self.login('demo-despachador')
        token = self.csrf_token()
        r = self.client.post('/api/v1/recoleccion/geocodificar',
                             json={'direccion': '  '},
                             headers={'X-CSRFToken': token})
        self.assertEqual(r.status_code, 400)

    def test_reversa_ok(self):
        self.login('demo-despachador')
        token = self.csrf_token()
        r = self.client.post('/api/v1/recoleccion/reversa',
                             json={'lat': -33.45, 'lon': -70.66},
                             headers={'X-CSRFToken': token})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()['ok'])

    def test_reversa_coordenadas_invalidas(self):
        self.login('demo-despachador')
        token = self.csrf_token()
        r = self.client.post('/api/v1/recoleccion/reversa',
                             json={'lat': 'abc', 'lon': 'xyz'},
                             headers={'X-CSRFToken': token})
        self.assertEqual(r.status_code, 400)


class TestApiEventos(RecoleccionTestCase):

    def test_evento_parada_idempotente(self):
        self.login('demo-despachador')
        token = self.csrf_token()
        ruta = self.planificar_y_publicar()
        parada_id = ruta.version_vigente.paradas[0].id
        cuerpo = {'tipo': 'llegada', 'idempotencia_key': 'clave-unica-1'}
        r1 = self.api('POST', '/api/v1/recoleccion/paradas/%d/evento' % parada_id,
                      cuerpo, token)
        self.assertEqual(r1.status_code, 200)
        self.assertFalse(r1.get_json().get('duplicado'))
        r2 = self.api('POST', '/api/v1/recoleccion/paradas/%d/evento' % parada_id,
                      cuerpo, token)
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(r2.get_json()['duplicado'])

        from apps.recoleccion.models import EventoRuta, ParadaRuta
        total = EventoRuta.query.filter_by(idempotencia_key='clave-unica-1').count()
        self.assertEqual(total, 1)
        parada = ParadaRuta.query.get(parada_id)
        self.assertEqual(parada.estado, 'en_atencion')

    def test_evento_completar_actualiza_solicitud(self):
        self.login('demo-despachador')
        token = self.csrf_token()
        ruta = self.planificar_y_publicar()
        parada_id = ruta.version_vigente.paradas[0].id
        r = self.api('POST', '/api/v1/recoleccion/paradas/%d/evento' % parada_id,
                     {'tipo': 'recoleccion_completada',
                      'idempotencia_key': 'clave-2'}, token)
        self.assertEqual(r.status_code, 200)
        from apps.recoleccion.models import ParadaRuta
        parada = ParadaRuta.query.get(parada_id)
        db.session.refresh(parada.solicitud)
        self.assertEqual(parada.solicitud.estado_operacional, 'completada')

    def test_evento_tipo_invalido(self):
        self.login('demo-despachador')
        token = self.csrf_token()
        ruta = self.planificar_y_publicar()
        parada_id = ruta.version_vigente.paradas[0].id
        r = self.api('POST', '/api/v1/recoleccion/paradas/%d/evento' % parada_id,
                     {'tipo': 'explosion', 'idempotencia_key': 'k3'}, token)
        self.assertEqual(r.status_code, 400)

    def test_conductor_no_puede_eventos_en_ruta_ajena(self):
        self.login('demo-despachador')
        ruta = self.planificar_y_publicar()
        parada_id = ruta.version_vigente.paradas[0].id
        self.login('demo-conductor')
        token = self.csrf_token()
        r = self.api('POST', '/api/v1/recoleccion/paradas/%d/evento' % parada_id,
                     {'tipo': 'llegada', 'idempotencia_key': 'k4'}, token)
        self.assertEqual(r.status_code, 403)

    def test_conductor_evento_en_su_ruta_ok(self):
        self.login('demo-despachador')
        ruta = self.planificar_y_publicar()
        ruta.conductor_id = self.usuarios['Conductor'].id
        db.session.commit()
        parada_id = ruta.version_vigente.paradas[0].id
        self.login('demo-conductor')
        token = self.csrf_token()
        r = self.api('POST', '/api/v1/recoleccion/paradas/%d/evento' % parada_id,
                     {'tipo': 'llegada', 'idempotencia_key': 'k5'}, token)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()['parada']['estado'], 'en_atencion')


class TestApiPlanificacion(RecoleccionTestCase):

    def test_publicar_y_recalcular_via_api(self):
        self.login('demo-despachador')
        token = self.csrf_token()
        from apps.recoleccion.services.planning import optimizar_jornada
        optimizar_jornada(self.jornada.id)
        ruta = self.jornada.rutas[0]
        ruta_id = ruta.id
        propuesta_id = next(v.id for v in ruta.versiones if v.tipo == 'propuesta')

        r = self.api('POST', '/api/v1/recoleccion/rutas/%d/publicar' % ruta_id,
                     {'version_id': propuesta_id}, token)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()['ok'])

        r = self.api('POST', '/api/v1/recoleccion/rutas/%d/publicar' % ruta_id,
                     {}, token)
        self.assertEqual(r.status_code, 400)

        r = self.api('POST', '/api/v1/recoleccion/rutas/%d/recalcular' % ruta_id,
                     {}, token)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()['ok'])

    def test_version_api(self):
        self.login('demo-despachador')
        ruta = self.planificar_y_publicar()
        vigente_id = ruta.version_vigente.id
        r = self.client.get(
            '/api/v1/recoleccion/rutas/%d/version/%d' % (ruta.id, vigente_id))
        self.assertEqual(r.status_code, 200)
        datos = r.get_json()
        self.assertTrue(datos['ok'])
        self.assertEqual(datos['version']['tipo'], 'publicada')

    def test_conductor_restringido_en_api_despachador(self):
        self.login('demo-despachador')
        token = self.csrf_token()
        self.login('demo-conductor')
        r = self.api('POST', '/api/v1/recoleccion/geocodificar',
                     {'direccion': 'Av. Pajaritos 2100'}, token)
        self.assertEqual(r.status_code, 403)


if __name__ == '__main__':
    unittest.main()
