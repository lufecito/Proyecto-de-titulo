# -*- encoding: utf-8 -*-
"""Verificación de render de vistas de recolección (modo demo)."""
import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

with tempfile.TemporaryDirectory() as td:
    os.environ['DEBUG'] = 'True'
    os.environ['SECRET_KEY'] = 'test'
    os.environ['MAP_PROVIDER'] = 'fake'
    os.environ['SQLITE_PATH'] = str(Path(td) / 'render.sqlite3')

    from run import app
    from apps import db

    with app.app_context():
        db.create_all()
        from apps.recoleccion.cli import ejecutar_seed_demo
        ejecutar_seed_demo()

    client = app.test_client()

    def login(usuario):
        return client.post('/login', data={
            'login': '1', 'username': usuario, 'password': 'Demo1234!'},
            follow_redirects=True)

    r = login('demo-despachador')
    print('login despachador:', r.status_code)

    paginas = [
        '/recoleccion',
        '/recoleccion/solicitudes',
        '/recoleccion/solicitudes/nueva',
        '/recoleccion/vehiculos',
        '/recoleccion/vehiculos/nuevo',
        '/recoleccion/jornadas',
        '/recoleccion/jornadas/nueva',
        '/recoleccion/jornadas/1',
        '/recoleccion/planificacion?jornada_id=1',
        '/recoleccion/historial',
        '/recoleccion/mi-ruta',
    ]
    for ruta in paginas:
        resp = client.get(ruta)
        ok = resp.status_code == 200
        print(('OK ' if ok else 'FAIL ') + ruta + ' -> ' + str(resp.status_code))
        if not ok:
            print(resp.data[:500])

    # la ruta/mapa 404 antes de optimizar es esperado (no existen rutas)
    print('mapa antes de optimizar (esperado 404):',
          client.get('/recoleccion/rutas/1/mapa').status_code)

    # optimizar + publicar + revisar mapa con versión
    with app.app_context():
        from apps.recoleccion.models import Jornada
        from apps.recoleccion.services.planning import optimizar_jornada, publicar_version
        jornada = Jornada.query.first()
        resumen = optimizar_jornada(jornada.id)
        print('optimizar:', resumen['ok'], resumen['optimizado']['estado_solver'])
        ruta = jornada.rutas[0]
        prop = next(v for v in ruta.versiones if v.tipo == 'propuesta')
        pub = publicar_version(ruta.id, prop.id)
        print('publicar:', pub['ok'])
    resp = client.get('/recoleccion/planificacion?jornada_id=1')
    print('planificacion tras optimizar:', resp.status_code)
    resp = client.get('/recoleccion/rutas/1/mapa')
    print('mapa:', resp.status_code)
    resp = client.get('/recoleccion/mi-ruta')
    print('mi-ruta despachador:', resp.status_code)

    # conductor
    r = login('demo-conductor')
    print('login conductor:', r.status_code)
    resp = client.get('/recoleccion/mi-ruta')
    print('mi-ruta conductor:', resp.status_code)

    # API con CSRF (token tomado del meta tag de una página renderizada en la misma sesión)
    login('demo-despachador')
    import re
    html = client.get('/recoleccion').data.decode('utf-8')
    m = re.search(r'name="csrf-token" content="([^"]+)"', html)
    if not m:
        m = re.search(r'name="csrf-token" content="([^"]+)"',
                      client.get('/recoleccion/mi-ruta').data.decode('utf-8'))
    token = m.group(1) if m else ''
    print('token encontrado:', bool(token), token[:12] + '...')
    resp = client.post('/api/v1/recoleccion/geocodificar',
                       json={'direccion': 'Plaza de Armas, Santiago'},
                       headers={'X-CSRFToken': token})
    print('api geocodificar:', resp.status_code, repr(resp.data[:200]))
    resp = client.post('/api/v1/recoleccion/geocodificar',
                       json={'direccion': 'Plaza de Armas, Santiago'})
    print('api sin csrf:', resp.status_code)

    with app.app_context():
        db.session.remove()
        db.engine.dispose()

print('RENDER OK')
