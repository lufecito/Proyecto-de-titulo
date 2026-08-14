"""recoleccion: creacion de esquema del modulo de recoleccion

Revision ID: 9f4c2a7b1e00
Revises:
Create Date: 2026-08-14

Nota: las tablas del modulo se crean con guardas de ``inspector`` para poder
aplicar esta migracion sobre una base de datos ya inicializada con
``db.create_all()`` (idempotente). La migracion solo crea las tablas que
faltan y aplica los ajustes conocidos de esquema (p. ej. la eliminacion de
``solicitudes_recoleccion.punto_id``), de modo que el comando
``flask db upgrade`` es seguro tanto en instalaciones nuevas como existentes.
"""
import logging

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

log = logging.getLogger('alembic')

revision = '9f4c2a7b1e00'
down_revision = None
branch_labels = None
depends_on = None

TABLAS_RECOLECCION = {
    'solicitudes_recoleccion', 'puntos_recoleccion', 'vehiculos', 'jornadas',
    'rutas', 'rutas_versiones', 'paradas_ruta', 'eventos_ruta',
    'ejecuciones_optimizacion', 'jornada_solicitudes', 'jornada_vehiculos',
}


def _existe(tabla, inspector=None):
    inspector = inspector or inspect(op.get_bind())
    return tabla in inspector.get_table_names()


def _columnas(tabla, inspector=None):
    inspector = inspector or inspect(op.get_bind())
    if not _existe(tabla, inspector):
        return set()
    return {col['name'] for col in inspector.get_columns(tabla)}


def _crear_si_falta(tabla, crear, inspector=None):
    if _existe(tabla, inspector):
        log.info('recoleccion: la tabla %s ya existe; se omite', tabla)
        return False
    crear()
    log.info('recoleccion: tabla %s creada', tabla)
    return True


def _tabla_solicitudes():
    op.create_table(
        'solicitudes_recoleccion',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('ticket_id', sa.Integer(), sa.ForeignKey('tickets.id'),
                  nullable=False, unique=True, index=True),
        sa.Column('estado_disponibilidad', sa.String(length=30), nullable=False),
        sa.Column('demanda', sa.Float(), nullable=False),
        sa.Column('unidad_demanda', sa.String(length=20), nullable=False),
        sa.Column('duracion_servicio_seg', sa.Integer(), nullable=False),
        sa.Column('ventana_inicio', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ventana_fin', sa.DateTime(timezone=True), nullable=True),
        sa.Column('prioridad', sa.Integer(), nullable=False),
        sa.Column('estado_operacional', sa.String(length=30), nullable=False),
        sa.Column('creado_en', sa.DateTime(timezone=True), nullable=False),
        sa.Column('actualizado_en', sa.DateTime(timezone=True), nullable=False),
    )


def _tabla_puntos():
    op.create_table(
        'puntos_recoleccion',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('solicitud_id', sa.Integer(),
                  sa.ForeignKey('solicitudes_recoleccion.id'),
                  nullable=False, unique=True, index=True),
        sa.Column('direccion_original', sa.String(length=240), nullable=True),
        sa.Column('direccion_normalizada', sa.String(length=240), nullable=True),
        sa.Column('comuna', sa.String(length=120), nullable=True),
        sa.Column('region', sa.String(length=120), nullable=True),
        sa.Column('referencia', sa.String(length=240), nullable=True),
        sa.Column('latitud', sa.Float(), nullable=False),
        sa.Column('longitud', sa.Float(), nullable=False),
        sa.Column('proveedor', sa.String(length=40), nullable=True),
        sa.Column('precision', sa.String(length=40), nullable=True),
        sa.Column('estado_validacion', sa.String(length=30), nullable=False),
        sa.Column('confirmado_por', sa.Integer(), sa.ForeignKey('usuarios.id'),
                  nullable=True),
        sa.Column('confirmado_en', sa.DateTime(timezone=True), nullable=True),
    )


def _tabla_vehiculos():
    op.create_table(
        'vehiculos',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('identificador', sa.String(length=40), nullable=False, unique=True),
        sa.Column('patente', sa.String(length=20), nullable=True, unique=True),
        sa.Column('nombre', sa.String(length=120), nullable=False),
        sa.Column('capacidad', sa.Float(), nullable=False),
        sa.Column('unidad', sa.String(length=20), nullable=False),
        sa.Column('estado_disponibilidad', sa.String(length=30), nullable=False),
        sa.Column('perfil_ruteo', sa.String(length=40), nullable=False),
        sa.Column('lat_inicio', sa.Float(), nullable=False),
        sa.Column('lon_inicio', sa.Float(), nullable=False),
        sa.Column('lat_fin', sa.Float(), nullable=False),
        sa.Column('lon_fin', sa.Float(), nullable=False),
        sa.Column('conductor_id', sa.Integer(), sa.ForeignKey('usuarios.id'),
                  nullable=True),
        sa.Column('creado_en', sa.DateTime(timezone=True), nullable=False),
        sa.Column('actualizado_en', sa.DateTime(timezone=True), nullable=False),
    )


def _tabla_jornadas():
    op.create_table(
        'jornadas',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('fecha_operacional', sa.Date(), nullable=False),
        sa.Column('estado', sa.String(length=30), nullable=False),
        sa.Column('zona_horaria', sa.String(length=60), nullable=False),
        sa.Column('inicio_operacion', sa.DateTime(timezone=True), nullable=False),
        sa.Column('fin_operacion', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deposito_direccion', sa.String(length=240), nullable=True),
        sa.Column('deposito_lat', sa.Float(), nullable=False),
        sa.Column('deposito_lon', sa.Float(), nullable=False),
        sa.Column('responsable_id', sa.Integer(), sa.ForeignKey('usuarios.id'),
                  nullable=True),
        sa.Column('creado_en', sa.DateTime(timezone=True), nullable=False),
        sa.Column('actualizado_en', sa.DateTime(timezone=True), nullable=False),
    )


def _tabla_rutas():
    op.create_table(
        'rutas',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('jornada_id', sa.Integer(), sa.ForeignKey('jornadas.id'),
                  nullable=False, index=True),
        sa.Column('vehiculo_id', sa.Integer(), sa.ForeignKey('vehiculos.id'),
                  nullable=False),
        sa.Column('conductor_id', sa.Integer(), sa.ForeignKey('usuarios.id'),
                  nullable=True),
        sa.Column('estado', sa.String(length=30), nullable=False),
        sa.Column('version_vigente_id', sa.Integer(), nullable=True),
        sa.Column('creado_en', sa.DateTime(timezone=True), nullable=False),
    )


def _tabla_versiones():
    op.create_table(
        'rutas_versiones',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('ruta_id', sa.Integer(), sa.ForeignKey('rutas.id'),
                  nullable=False, index=True),
        sa.Column('numero', sa.Integer(), nullable=False),
        sa.Column('tipo', sa.String(length=20), nullable=False, index=True),
        sa.Column('estrategia', sa.String(length=60), nullable=False),
        sa.Column('version_estrategia', sa.String(length=40), nullable=False),
        sa.Column('parametros', sa.JSON(), nullable=True),
        sa.Column('estado_solver', sa.String(length=40), nullable=False),
        sa.Column('distancia_metros', sa.Float(), nullable=False),
        sa.Column('duracion_seg', sa.Float(), nullable=False),
        sa.Column('carga_total', sa.Float(), nullable=False),
        sa.Column('carga_unidad', sa.String(length=20), nullable=False),
        sa.Column('geometria_geojson', sa.JSON(), nullable=True),
        sa.Column('no_asignadas', sa.JSON(), nullable=True),
        sa.Column('creado_por', sa.Integer(), sa.ForeignKey('usuarios.id'),
                  nullable=True),
        sa.Column('creado_en', sa.DateTime(timezone=True), nullable=False),
        sa.Column('es_vigente', sa.Boolean(), nullable=False),
        sa.UniqueConstraint('ruta_id', 'numero', name='uq_ruta_version_numero'),
    )


def _tabla_paradas():
    op.create_table(
        'paradas_ruta',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('version_id', sa.Integer(), sa.ForeignKey('rutas_versiones.id'),
                  nullable=False, index=True),
        sa.Column('solicitud_id', sa.Integer(),
                  sa.ForeignKey('solicitudes_recoleccion.id'), nullable=False),
        sa.Column('posicion', sa.Integer(), nullable=False),
        sa.Column('distancia_acumulada', sa.Float(), nullable=False),
        sa.Column('duracion_acumulada', sa.Float(), nullable=False),
        sa.Column('carga_acumulada', sa.Float(), nullable=False),
        sa.Column('hora_llegada_estimada', sa.DateTime(timezone=True),
                  nullable=True),
        sa.Column('estado', sa.String(length=30), nullable=False),
        sa.Column('resultado', sa.String(length=120), nullable=True),
        sa.Column('actualizado_en', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('version_id', 'solicitud_id',
                            name='uq_parada_version_solicitud'),
        sa.UniqueConstraint('version_id', 'posicion',
                            name='uq_parada_version_posicion'),
    )


def _tabla_eventos():
    op.create_table(
        'eventos_ruta',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('ruta_id', sa.Integer(), sa.ForeignKey('rutas.id'),
                  nullable=False, index=True),
        sa.Column('parada_id', sa.Integer(), sa.ForeignKey('paradas_ruta.id'),
                  nullable=True),
        sa.Column('version_id', sa.Integer(), sa.ForeignKey('rutas_versiones.id'),
                  nullable=True),
        sa.Column('actor_id', sa.Integer(), sa.ForeignKey('usuarios.id'),
                  nullable=True),
        sa.Column('tipo', sa.String(length=40), nullable=False),
        sa.Column('fecha_utc', sa.DateTime(timezone=True), nullable=False),
        sa.Column('idempotencia_key', sa.String(length=120), nullable=False,
                  unique=True),
        sa.Column('latitud', sa.Float(), nullable=True),
        sa.Column('longitud', sa.Float(), nullable=True),
        sa.Column('observacion', sa.Text(), nullable=True),
        sa.Column('datos_anteriores', sa.JSON(), nullable=True),
        sa.Column('datos_nuevos', sa.JSON(), nullable=True),
    )


def _tabla_ejecuciones():
    op.create_table(
        'ejecuciones_optimizacion',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('jornada_id', sa.Integer(), sa.ForeignKey('jornadas.id'),
                  nullable=True),
        sa.Column('ruta_id', sa.Integer(), sa.ForeignKey('rutas.id'),
                  nullable=True),
        sa.Column('hash_entrada', sa.String(length=64), nullable=False,
                  index=True),
        sa.Column('estrategia', sa.String(length=60), nullable=False),
        sa.Column('version_estrategia', sa.String(length=40), nullable=False),
        sa.Column('parametros', sa.JSON(), nullable=True),
        sa.Column('estado_solver', sa.String(length=40), nullable=False),
        sa.Column('duracion_seg', sa.Float(), nullable=False),
        sa.Column('objetivo', sa.Float(), nullable=True),
        sa.Column('advertencias', sa.JSON(), nullable=True),
        sa.Column('resultado', sa.JSON(), nullable=True),
        sa.Column('creado_en', sa.DateTime(timezone=True), nullable=False),
    )


def _tabla_jornada_solicitudes():
    op.create_table(
        'jornada_solicitudes',
        sa.Column('jornada_id', sa.Integer(),
                  sa.ForeignKey('jornadas.id', ondelete='CASCADE'),
                  primary_key=True),
        sa.Column('solicitud_id', sa.Integer(),
                  sa.ForeignKey('solicitudes_recoleccion.id', ondelete='CASCADE'),
                  primary_key=True),
    )


def _tabla_jornada_vehiculos():
    op.create_table(
        'jornada_vehiculos',
        sa.Column('jornada_id', sa.Integer(),
                  sa.ForeignKey('jornadas.id', ondelete='CASCADE'),
                  primary_key=True),
        sa.Column('vehiculo_id', sa.Integer(),
                  sa.ForeignKey('vehiculos.id', ondelete='CASCADE'),
                  primary_key=True),
    )


def upgrade():
    inspector = inspect(op.get_bind())

    # 1) Ajustes conocidos sobre tablas preexistentes
    col_solicitudes = _columnas('solicitudes_recoleccion', inspector)
    if 'punto_id' in col_solicitudes:
        op.drop_column('solicitudes_recoleccion', 'punto_id')
        log.info('recoleccion: columna punto_id eliminada de solicitudes_recoleccion')

    # 2) Creacion de tablas (solo las que faltan)
    _crear_si_falta('solicitudes_recoleccion', _tabla_solicitudes, inspector)
    _crear_si_falta('puntos_recoleccion', _tabla_puntos, inspector)
    _crear_si_falta('vehiculos', _tabla_vehiculos, inspector)
    _crear_si_falta('jornadas', _tabla_jornadas, inspector)
    _crear_si_falta('rutas', _tabla_rutas, inspector)
    _crear_si_falta('rutas_versiones', _tabla_versiones, inspector)
    _crear_si_falta('paradas_ruta', _tabla_paradas, inspector)
    _crear_si_falta('eventos_ruta', _tabla_eventos, inspector)
    _crear_si_falta('ejecuciones_optimizacion', _tabla_ejecuciones, inspector)
    _crear_si_falta('jornada_solicitudes', _tabla_jornada_solicitudes, inspector)
    _crear_si_falta('jornada_vehiculos', _tabla_jornada_vehiculos, inspector)

    # 3) FK circular rutas.version_vigente_id -> rutas_versiones
    inspector = inspect(op.get_bind())
    if _existe('rutas', inspector):
        col_rutas = _columnas('rutas', inspector)
        fk_rutas = {fk['constrained_columns'][0]
                    for fk in inspector.get_foreign_keys('rutas')}
        if 'version_vigente_id' in col_rutas and 'version_vigente_id' not in fk_rutas:
            try:
                op.create_foreign_key(
                    'fk_rutas_version_vigente', 'rutas', 'rutas_versiones',
                    ['version_vigente_id'], ['id'])
                log.info('recoleccion: FK version_vigente_id creada en rutas')
            except NotImplementedError:
                # SQLite no soporta ALTER de constraints; el esquema creado
                # por db.create_all() ya incluye la FK.
                log.warning('recoleccion: SQLite omite ALTER de FK en rutas')


def downgrade():
    inspector = inspect(op.get_bind())
    orden = [
        'jornada_vehiculos', 'jornada_solicitudes', 'ejecuciones_optimizacion',
        'eventos_ruta', 'paradas_ruta', 'rutas_versiones', 'rutas',
        'jornadas', 'vehiculos', 'puntos_recoleccion',
        'solicitudes_recoleccion',
    ]
    for tabla in orden:
        if _existe(tabla, inspector):
            op.drop_table(tabla)
            log.info('recoleccion: tabla %s eliminada', tabla)
        inspector = inspect(op.get_bind())
