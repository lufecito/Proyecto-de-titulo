# -*- encoding: utf-8 -*-
"""
Entidades del módulo de recolección.

Nombres de tablas en español, consistentes con las tablas existentes de
ticketflow (clientes, tickets, usuarios). Las fechas se almacenan con zona
horaria explícita (UTC). En SQLite el tiempo se devuelve naive al leer;
los helpers utcnow()/as_utc() normalizan ese comportamiento. En PostgreSQL
la zona horaria se conserva de forma nativa.
"""

import json
from datetime import datetime, timezone

from apps import db

# ---------------------------------------------------------------------------
# Helpers de fecha/hora (UTC con zona horaria explícita)
# ---------------------------------------------------------------------------


def utcnow():
    """Timestamp actual con zona horaria UTC explícita."""
    return datetime.now(timezone.utc)


def as_utc(value):
    """Normaliza un datetime a UTC. SQLite devuelve naive: se asume UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def to_local(value, zona_horaria='America/Santiago'):
    """Convierte un datetime UTC a la zona horaria operacional."""
    from zoneinfo import ZoneInfo
    return as_utc(value).astimezone(ZoneInfo(zona_horaria))


def from_local(value, zona_horaria='America/Santiago'):
    """Interpreta un datetime naive como hora local y lo convierte a UTC."""
    from zoneinfo import ZoneInfo
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo(zona_horaria))
    return value.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Estados
# ---------------------------------------------------------------------------

SOLICITUD_ESTADOS_OPERACIONALES = [
    'pendiente', 'disponible', 'asignada', 'completada', 'no_realizada', 'cancelada',
]
SOLICITUD_DISPONIBILIDAD = ['disponible', 'no_disponible']
PUNTO_ESTADOS_VALIDACION = ['pendiente', 'validado', 'no_validado']
VEHICULO_ESTADOS = ['disponible', 'no_disponible', 'en_ruta']
JORNADA_ESTADOS = ['preparacion', 'planificada', 'publicada', 'en_ejecucion', 'completada', 'cancelada']
RUTA_ESTADOS = ['borrador', 'propuesta', 'publicada', 'en_ejecucion', 'completada', 'cancelada']
VERSION_TIPOS = ['linea_base', 'propuesta', 'publicada']
PARADA_ESTADOS = ['pendiente', 'en_atencion', 'completada', 'no_disponible', 'omitida', 'incidencia']
EVENTO_TIPOS = ['llegada', 'recoleccion_completada', 'punto_no_disponible', 'incidencia',
                'publicacion', 'recalculo', 'optimizacion', 'creacion']
PRIORIDAD_NORMALIZADA = [1, 2, 3, 4]


# ---------------------------------------------------------------------------
# Asociaciones Jornada <-> Solicitudes / Vehiculos
# ---------------------------------------------------------------------------

jornada_solicitudes = db.Table(
    'jornada_solicitudes',
    db.Column('jornada_id', db.Integer, db.ForeignKey('jornadas.id', ondelete='CASCADE'),
              primary_key=True),
    db.Column('solicitud_id', db.Integer, db.ForeignKey('solicitudes_recoleccion.id', ondelete='CASCADE'),
              primary_key=True),
    db.UniqueConstraint('jornada_id', 'solicitud_id', name='uq_jornada_solicitud'),
)

jornada_vehiculos = db.Table(
    'jornada_vehiculos',
    db.Column('jornada_id', db.Integer, db.ForeignKey('jornadas.id', ondelete='CASCADE'),
              primary_key=True),
    db.Column('vehiculo_id', db.Integer, db.ForeignKey('vehiculos.id', ondelete='CASCADE'),
              primary_key=True),
    db.UniqueConstraint('jornada_id', 'vehiculo_id', name='uq_jornada_vehiculo'),
)


class SolicitudRecoleccion(db.Model):
    """Unidad de trabajo derivada de un ticket existente (uno por ticket)."""

    __tablename__ = 'solicitudes_recoleccion'

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), unique=True, nullable=False,
                          index=True)

    estado_disponibilidad = db.Column(db.String(30), default='disponible', nullable=False)
    demanda = db.Column(db.Float, default=0, nullable=False)
    unidad_demanda = db.Column(db.String(20), default='kg', nullable=False)
    duracion_servicio_seg = db.Column(db.Integer, default=900, nullable=False)
    ventana_inicio = db.Column(db.DateTime(timezone=True))
    ventana_fin = db.Column(db.DateTime(timezone=True))
    prioridad = db.Column(db.Integer, default=3, nullable=False)
    estado_operacional = db.Column(db.String(30), default='pendiente', nullable=False, index=True)

    creado_en = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    actualizado_en = db.Column(db.DateTime(timezone=True), default=utcnow,
                               onupdate=utcnow, nullable=False)

    ticket = db.relationship('Ticket', backref=db.backref('solicitud_recoleccion',
                                                          uselist=False))
    punto = db.relationship('PuntoRecoleccion', back_populates='solicitud',
                            uselist=False, cascade='all, delete-orphan')

    @property
    def etiqueta(self):
        return self.ticket.numero if self.ticket else f'Solicitud {self.id}'


class PuntoRecoleccion(db.Model):
    """Ubicación operativa asociada a una solicitud."""

    __tablename__ = 'puntos_recoleccion'

    id = db.Column(db.Integer, primary_key=True)
    solicitud_id = db.Column(db.Integer, db.ForeignKey('solicitudes_recoleccion.id'),
                             unique=True, nullable=False, index=True)

    direccion_original = db.Column(db.String(240))
    direccion_normalizada = db.Column(db.String(240))
    comuna = db.Column(db.String(120))
    region = db.Column(db.String(120))
    referencia = db.Column(db.String(240))
    latitud = db.Column(db.Float, nullable=False)
    longitud = db.Column(db.Float, nullable=False)
    proveedor = db.Column(db.String(40), default='manual')
    precision = db.Column(db.String(40), default='manual')
    estado_validacion = db.Column(db.String(30), default='pendiente', nullable=False, index=True)

    confirmado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    confirmado_en = db.Column(db.DateTime(timezone=True))

    solicitud = db.relationship('SolicitudRecoleccion', back_populates='punto')
    confirmado_por_usuario = db.relationship('Users', foreign_keys=[confirmado_por])


class Vehiculo(db.Model):
    """Camión con capacidad y punto de inicio/término."""

    __tablename__ = 'vehiculos'

    id = db.Column(db.Integer, primary_key=True)
    identificador = db.Column(db.String(40), unique=True, nullable=False)
    patente = db.Column(db.String(20), unique=True)
    nombre = db.Column(db.String(120), nullable=False)
    capacidad = db.Column(db.Float, default=1000, nullable=False)
    unidad = db.Column(db.String(20), default='kg', nullable=False)
    estado_disponibilidad = db.Column(db.String(30), default='disponible', nullable=False)
    perfil_ruteo = db.Column(db.String(40), default='driving-hgv', nullable=False)

    lat_inicio = db.Column(db.Float, nullable=False)
    lon_inicio = db.Column(db.Float, nullable=False)
    lat_fin = db.Column(db.Float, nullable=False)
    lon_fin = db.Column(db.Float, nullable=False)

    conductor_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    creado_en = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    actualizado_en = db.Column(db.DateTime(timezone=True), default=utcnow,
                               onupdate=utcnow, nullable=False)

    conductor = db.relationship('Users', foreign_keys=[conductor_id])
    rutas = db.relationship('Ruta', back_populates='vehiculo', lazy=True)


class Jornada(db.Model):
    """Operación de un periodo: agrupa solicitudes, vehículos y rutas."""

    __tablename__ = 'jornadas'

    id = db.Column(db.Integer, primary_key=True)
    fecha_operacional = db.Column(db.Date, nullable=False)
    estado = db.Column(db.String(30), default='preparacion', nullable=False)
    zona_horaria = db.Column(db.String(60), default='America/Santiago', nullable=False)

    inicio_operacion = db.Column(db.DateTime(timezone=True), nullable=False)
    fin_operacion = db.Column(db.DateTime(timezone=True))

    deposito_direccion = db.Column(db.String(240))
    deposito_lat = db.Column(db.Float, nullable=False)
    deposito_lon = db.Column(db.Float, nullable=False)

    responsable_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    creado_en = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    actualizado_en = db.Column(db.DateTime(timezone=True), default=utcnow,
                               onupdate=utcnow, nullable=False)

    responsable = db.relationship('Users', foreign_keys=[responsable_id])
    solicitudes = db.relationship('SolicitudRecoleccion',
                                  secondary=jornada_solicitudes,
                                  backref=db.backref('jornadas', lazy=True))
    vehiculos = db.relationship('Vehiculo', secondary=jornada_vehiculos,
                                backref=db.backref('jornadas', lazy=True))
    rutas = db.relationship('Ruta', back_populates='jornada', lazy=True)


class Ruta(db.Model):
    """Asignación de un vehículo y conductor dentro de una jornada."""

    __tablename__ = 'rutas'

    id = db.Column(db.Integer, primary_key=True)
    jornada_id = db.Column(db.Integer, db.ForeignKey('jornadas.id'), nullable=False, index=True)
    vehiculo_id = db.Column(db.Integer, db.ForeignKey('vehiculos.id'), nullable=False)
    conductor_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    estado = db.Column(db.String(30), default='borrador', nullable=False)
    version_vigente_id = db.Column(db.Integer, db.ForeignKey('rutas_versiones.id'),
                                   nullable=True, index=True)
    creado_en = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    jornada = db.relationship('Jornada', back_populates='rutas')
    vehiculo = db.relationship('Vehiculo', back_populates='rutas')
    conductor = db.relationship('Users', foreign_keys=[conductor_id])
    versiones = db.relationship('RutaVersion', back_populates='ruta',
                                foreign_keys='RutaVersion.ruta_id',
                                order_by='RutaVersion.numero')
    version_vigente = db.relationship('RutaVersion',
                                      foreign_keys=[version_vigente_id],
                                      post_update=True)


class RutaVersion(db.Model):
    """Instancia inmutable de una ruta (línea base, propuesta o publicada)."""

    __tablename__ = 'rutas_versiones'

    id = db.Column(db.Integer, primary_key=True)
    ruta_id = db.Column(db.Integer, db.ForeignKey('rutas.id'), nullable=False, index=True)
    numero = db.Column(db.Integer, nullable=False)
    tipo = db.Column(db.String(20), nullable=False, index=True)

    estrategia = db.Column(db.String(60), nullable=False)
    version_estrategia = db.Column(db.String(40), nullable=False)
    parametros = db.Column(db.JSON)
    estado_solver = db.Column(db.String(40), nullable=False)

    distancia_metros = db.Column(db.Float, default=0, nullable=False)
    duracion_seg = db.Column(db.Float, default=0, nullable=False)
    carga_total = db.Column(db.Float, default=0, nullable=False)
    carga_unidad = db.Column(db.String(20), default='kg', nullable=False)
    geometria_geojson = db.Column(db.JSON)
    no_asignadas = db.Column(db.JSON)

    creado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    creado_en = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    es_vigente = db.Column(db.Boolean, default=False, nullable=False)

    ruta = db.relationship('Ruta', back_populates='versiones', foreign_keys=[ruta_id])
    creado_por_usuario = db.relationship('Users', foreign_keys=[creado_por])
    paradas = db.relationship('ParadaRuta', back_populates='version',
                              order_by='ParadaRuta.posicion',
                              cascade='all, delete-orphan', lazy=True)

    __table_args__ = (
        db.UniqueConstraint('ruta_id', 'numero', name='uq_ruta_version_numero'),
    )


class ParadaRuta(db.Model):
    """Servicio planificado dentro de una versión de ruta."""

    __tablename__ = 'paradas_ruta'

    id = db.Column(db.Integer, primary_key=True)
    version_id = db.Column(db.Integer, db.ForeignKey('rutas_versiones.id'),
                           nullable=False, index=True)
    solicitud_id = db.Column(db.Integer, db.ForeignKey('solicitudes_recoleccion.id'),
                             nullable=False)
    posicion = db.Column(db.Integer, nullable=False)

    distancia_acumulada = db.Column(db.Float, default=0, nullable=False)
    duracion_acumulada = db.Column(db.Float, default=0, nullable=False)
    carga_acumulada = db.Column(db.Float, default=0, nullable=False)
    hora_llegada_estimada = db.Column(db.DateTime(timezone=True))

    estado = db.Column(db.String(30), default='pendiente', nullable=False)
    resultado = db.Column(db.String(120))
    actualizado_en = db.Column(db.DateTime(timezone=True), default=utcnow,
                               onupdate=utcnow, nullable=False)

    version = db.relationship('RutaVersion', back_populates='paradas')
    solicitud = db.relationship('SolicitudRecoleccion')

    __table_args__ = (
        db.UniqueConstraint('version_id', 'solicitud_id', name='uq_parada_version_solicitud'),
        db.UniqueConstraint('version_id', 'posicion', name='uq_parada_version_posicion'),
    )


class EventoRuta(db.Model):
    """Evento operacional auditable e idempotente."""

    __tablename__ = 'eventos_ruta'

    id = db.Column(db.Integer, primary_key=True)
    ruta_id = db.Column(db.Integer, db.ForeignKey('rutas.id'), nullable=False, index=True)
    parada_id = db.Column(db.Integer, db.ForeignKey('paradas_ruta.id'), nullable=True)
    version_id = db.Column(db.Integer, db.ForeignKey('rutas_versiones.id'), nullable=True)
    actor_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)

    tipo = db.Column(db.String(40), nullable=False)
    fecha_utc = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    idempotencia_key = db.Column(db.String(120), unique=True, nullable=False)
    latitud = db.Column(db.Float)
    longitud = db.Column(db.Float)
    observacion = db.Column(db.Text)
    datos_anteriores = db.Column(db.JSON)
    datos_nuevos = db.Column(db.JSON)

    ruta = db.relationship('Ruta')
    parada = db.relationship('ParadaRuta')
    version = db.relationship('RutaVersion')
    actor = db.relationship('Users', foreign_keys=[actor_id])


class EjecucionOptimizacion(db.Model):
    """Registro de una ejecución del optimizador (reproducibilidad)."""

    __tablename__ = 'ejecuciones_optimizacion'

    id = db.Column(db.Integer, primary_key=True)
    jornada_id = db.Column(db.Integer, db.ForeignKey('jornadas.id'), nullable=True)
    ruta_id = db.Column(db.Integer, db.ForeignKey('rutas.id'), nullable=True)

    hash_entrada = db.Column(db.String(64), nullable=False, index=True)
    estrategia = db.Column(db.String(60), nullable=False)
    version_estrategia = db.Column(db.String(40), nullable=False)
    parametros = db.Column(db.JSON)
    estado_solver = db.Column(db.String(40), nullable=False)
    duracion_seg = db.Column(db.Float, nullable=False)
    objetivo = db.Column(db.Float)
    advertencias = db.Column(db.JSON)
    resultado = db.Column(db.JSON)

    creado_en = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)


def _json_dumps(value):
    return json.dumps(value, default=str)
