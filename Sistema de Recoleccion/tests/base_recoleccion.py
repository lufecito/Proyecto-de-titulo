# -*- encoding: utf-8 -*-
"""Base compartida de pruebas del módulo de recolección.

Cada clase de test crea su propia aplicación con SQLite temporal y el
proveedor cartográfico fake (sin red). Las variables de entorno se fijan
antes de importar `apps` para que la configuración se lea correctamente.
"""
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ['MAP_PROVIDER'] = 'fake'
os.environ.setdefault('SECRET_KEY', 'test-secret')
os.environ.setdefault('DEBUG', 'True')

from apps import create_app, db  # noqa: E402
from apps.config import config_dict  # noqa: E402


class RecoleccionTestCase(unittest.TestCase):
    """Base con app de prueba (SQLite temporal + proveedor fake, sin red)."""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory(prefix='rec_test_')
        cls.db_path = Path(cls._tmpdir.name) / 'test.sqlite3'
        cls.app = create_app(config_dict['Debug'])
        cls.app.config['SQLALCHEMY_DATABASE_URI'] = (
            'sqlite:///' + str(cls.db_path).replace('\\', '/'))
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = True

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        cls._tmpdir.cleanup()

    def setUp(self):
        """Contexto por test: limpia `g`, la sesión y la base de datos."""
        self._ctx = self.app.app_context()
        self._ctx.push()
        db.drop_all()
        db.create_all()
        from apps.recoleccion.cli import ejecutar_seed_demo
        jornada, usuarios = ejecutar_seed_demo()
        self._jornada_id = jornada.id
        self._usuarios_ids = {rol: u.id for rol, u in usuarios.items()}
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        self._ctx.pop()

    @property
    def jornada(self):
        """Re-obtiene la jornada (el app quita la sesión tras cada request)."""
        from apps.recoleccion.models import Jornada
        return db.session.get(Jornada, self._jornada_id)

    @property
    def usuarios(self):
        from apps.authentication.models import Users
        return {rol: db.session.get(Users, uid)
                for rol, uid in self._usuarios_ids.items()}

    # -- helpers -----------------------------------------------------------

    def login(self, username='demo-despachador', password='Demo1234!'):
        return self.client.post(
            '/login',
            data={'login': '1', 'username': username, 'password': password},
            follow_redirects=True)

    def csrf_token(self):
        """Obtiene un token CSRF desde el meta tag de una página del módulo."""
        html = self.client.get('/recoleccion/mi-ruta').data.decode('utf-8')
        m = re.search(r'name="csrf-token" content="([^"]+)"', html)
        return m.group(1) if m else ''

    def api(self, metodo, url, cuerpo=None, token=None):
        headers = {}
        if token is not None:
            headers['X-CSRFToken'] = token
        return self.client.open(url, method=metodo, json=cuerpo, headers=headers)

    def planificar_y_publicar(self):
        """Optimiza la jornada de demostración y publica la propuesta."""
        from apps.recoleccion.services.planning import (optimizar_jornada,
                                                         publicar_version)
        resumen = optimizar_jornada(self.jornada.id)
        assert resumen['ok'], resumen
        ruta = self.jornada.rutas[0]
        propuesta = next(v for v in ruta.versiones if v.tipo == 'propuesta')
        publicar_version(ruta.id, propuesta.id)
        db.session.refresh(ruta)
        return ruta
