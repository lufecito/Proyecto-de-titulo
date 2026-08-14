# -*- encoding: utf-8 -*-
"""Prueba integrada del flujo de planificación (modo demo / sin red)."""
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
    os.environ['SQLITE_PATH'] = str(Path(td) / 'flow.sqlite3')

    from run import app
    from apps import db

    with app.app_context():
        db.create_all()
        from apps.recoleccion.cli import ejecutar_seed_demo
        ejecutar_seed_demo()

        from apps.recoleccion.models import Jornada
        from apps.recoleccion.services.planning import (optimizar_jornada,
                                                        publicar_version,
                                                        recalcular_ruta,
                                                        version_a_json)

        jornada = Jornada.query.first()
        print('jornada', jornada.id, 'solicitudes', len(jornada.solicitudes))

        resumen = optimizar_jornada(jornada.id)
        assert resumen['ok'], resumen
        print('optimizar ok:', resumen['proveedor'], resumen['perfil'])
        print('  linea base:', resumen['linea_base']['estado_solver'],
              resumen['linea_base']['distancia_total'])
        print('  optimizado:', resumen['optimizado']['estado_solver'],
              resumen['optimizado']['distancia_total'],
              'obj', resumen['optimizado']['objetivo'])
        print('  versiones:', [(v['vehiculo'], v['linea_base_version_id'],
                                v['propuesta_version_id'])
                               for v in resumen['versiones']])
        print('  no asignadas:', resumen['no_asignadas'])

        ruta = jornada.rutas[0]
        prop = next(v for v in ruta.versiones if v.tipo == 'propuesta')
        print('propuesta paradas:', [(p.posicion, p.solicitud.etiqueta)
                                     for p in prop.paradas])

        pub = publicar_version(ruta.id, prop.id)
        assert pub['ok'], pub
        print('publicar ok:', pub['version_id'], 'numero', pub['numero'])
        ruta_actual = __import__('apps.recoleccion.models',
                                 fromlist=['Ruta']).Ruta.query.get(ruta.id)
        print('vigente:', ruta_actual.version_vigente_id,
              ruta_actual.version_vigente.tipo)

        parada0 = ruta_actual.version_vigente.paradas[0]
        parada0.estado = 'completada'
        parada0.solicitud.estado_operacional = 'completada'
        db.session.commit()
        print('parada completada:', parada0.solicitud.etiqueta)

        rec = recalcular_ruta(ruta.id)
        print('recalcular:', rec['ok'], rec.get('cambio'), rec.get('no_asignadas'))
        nueva_prop = next(v for v in ruta.versiones
                          if v.tipo == 'propuesta' and v.numero == max(
                              x.numero for x in ruta.versiones
                              if x.tipo == 'propuesta'))
        print('nueva propuesta paradas:',
              [(p.posicion, p.solicitud.etiqueta, p.estado) for p in nueva_prop.paradas])

        pub2 = publicar_version(ruta.id, nueva_prop.id)
        assert pub2['ok']
        print('publicar v2 ok:', pub2['version_id'])

        versiones_pub = [v for v in ruta.versiones if v.tipo == 'publicada']
        print('versiones publicadas:', len(versiones_pub))

        # publicación inmutable: la primera publicada no cambió
        primera = versiones_pub[0]
        print('primera publicada paradas:', [(p.solicitud.etiqueta, p.estado)
                                             for p in primera.paradas])

        datos = version_a_json(ruta.version_vigente)
        print('json paradas:', [(p['posicion'], p['estado']) for p in datos['paradas']])
        print('json geometria:', bool(datos['geometria']))

        from apps.recoleccion.services.metrics import metricas_jornada
        m = metricas_jornada(jornada)
        print('metricas:', {k: m[k] for k in ('distancia_base_total_m',
                                              'distancia_propuesta_total_m',
                                              'diff_distancia_pct', 'recalculos',
                                              'publicaciones',
                                              'cantidad_no_asignadas')})
        db.session.remove()
        db.engine.dispose()

print('FLUJO OK')
