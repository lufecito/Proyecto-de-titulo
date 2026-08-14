# -*- encoding: utf-8 -*-
"""Comandos CLI del módulo de recolección (semilla de demostración)."""

import os
from datetime import date, datetime, time

import click
from flask.cli import with_appcontext

from apps import db
from apps.authentication.models import Users
from apps.home.models import Cliente, Ticket
from apps.recoleccion.models import (Jornada, PuntoRecoleccion,
                                     SolicitudRecoleccion, Vehiculo, from_local)

# (id interno, número de ticket, asunto, comuna, dirección, lat, lon, demanda,
#  prioridad)
DATOS_DEMO = [
    ('d1', 'REC-0001', 'Recolección residencial', 'Maipú',
     'Av. Pajaritos 2100', -33.4800, -70.7000, 180, 2),
    ('d2', 'REC-0002', 'Recolección residencial', 'Independencia',
     'Av. Independencia 1800', -33.4300, -70.6400, 120, 3),
    ('d3', 'REC-0003', 'Recolección comercial', 'Quilicura',
     'Camino a Valparaíso 5400', -33.3900, -70.6100, 240, 1),
    ('d4', 'REC-0004', 'Recolección domiciliaria', 'Cerrillos',
     'Av. Pedro Aguirre Cerda 3200', -33.5100, -70.6900, 150, 3),
    ('d5', 'REC-0005', 'Recolección comercial', 'Ñuñoa',
     'Av. Irarrázaval 2500', -33.4600, -70.6600, 200, 2),
    ('d6', 'REC-0006', 'Recolección industrial liviana', 'Colina',
     'Camino a Colina 6800', -33.4300, -70.5700, 300, 1),
    ('d7', 'REC-0007', 'Recolección residencial', 'San Bernardo',
     'Av. Portales 2100', -33.5300, -70.7200, 140, 3),
    ('d8', 'REC-0008', 'Recolección domiciliaria', 'Renca',
     'Av. Dorsal 3100', -33.4000, -70.6800, 160, 2),
]

DEPOSITO_DEMO = {
    'direccion': 'Plaza de Armas, Santiago',
    'lat': -33.4372,
    'lon': -70.6506,
}

DEMO_ROLES = [
    ('demo-admin', 'Administrador', 'DEMO_ADMIN_PASSWORD', 'Demo1234!'),
    ('demo-despachador', 'Despachador', 'DEMO_DESPACHADOR_PASSWORD', 'Demo1234!'),
    ('demo-conductor', 'Conductor', 'DEMO_CONDUCTOR_PASSWORD', 'Demo1234!'),
]


def _crear_usuario(username, rol, password):
    usuario = Users.query.filter_by(username=username).first()
    if not usuario:
        usuario = Users(username=username, email=f'{username}@example.com',
                        password=password, rol=rol, activo=True)
        db.session.add(usuario)
        db.session.flush()
        click.echo(f'> Usuario demo creado: {username} ({rol})')
    return usuario


def _crear_ticket_y_solicitud(item, cliente):
    _id, numero, asunto, comuna, direccion, lat, lon, demanda, prioridad = item
    ticket = Ticket.query.filter_by(numero=numero).first()
    if not ticket:
        ticket = Ticket(numero=numero, cliente=cliente, asunto=asunto,
                        estado='Ingresado', prioridad='Media',
                        modalidad='Presencial',
                        categoria='Respaldo y recuperación')
        db.session.add(ticket)
        db.session.flush()
        click.echo(f'> Ticket demo creado: {numero}')
    solicitud = SolicitudRecoleccion.query.filter_by(ticket_id=ticket.id).first()
    if not solicitud:
        solicitud = SolicitudRecoleccion(
            ticket_id=ticket.id, estado_disponibilidad='disponible',
            demanda=demanda, unidad_demanda='kg', duracion_servicio_seg=900,
            prioridad=prioridad, estado_operacional='pendiente')
        db.session.add(solicitud)
        db.session.flush()
        punto = PuntoRecoleccion(
            solicitud_id=solicitud.id, direccion_original=direccion,
            direccion_normalizada=direccion, comuna=comuna, region='Región Metropolitana',
            latitud=lat, longitud=lon, proveedor='demo', precision='demo',
            estado_validacion='validado')
        db.session.add(punto)
        click.echo(f'> Solicitud demo creada: {numero}')
    return solicitud


def _crear_jornada(solicitudes, vehiculo, conductor):
    hoy = date.today()
    fecha = Jornada.query.filter_by(fecha_operacional=hoy).first()
    if not fecha:
        inicio = from_local(datetime.combine(hoy, time(8, 0)))
        fin = from_local(datetime.combine(hoy, time(16, 0)))
        fecha = Jornada(
            fecha_operacional=hoy, estado='preparacion',
            inicio_operacion=inicio, fin_operacion=fin,
            deposito_direccion=DEPOSITO_DEMO['direccion'],
            deposito_lat=DEPOSITO_DEMO['lat'], deposito_lon=DEPOSITO_DEMO['lon'],
            responsable_id=conductor.id)
        db.session.add(fecha)
        db.session.flush()
        fecha.solicitudes = solicitudes
        fecha.vehiculos = [vehiculo]
        click.echo('> Jornada demo creada para hoy.')
    return fecha


def ejecutar_seed_demo():
    """Ejecuta la semilla de demostración (idempotente). Devuelve la jornada."""
    db.create_all()

    usuarios = {}
    for username, rol, env_var, password in DEMO_ROLES:
        clave = os.getenv(env_var, password)
        usuarios[rol] = _crear_usuario(username, rol, clave)

    cliente = Cliente.query.filter_by(rut='76.123.456-7').first()
    if not cliente:
        cliente = Cliente(nombre='Cliente Demo Reciclaje', rut='76.123.456-7',
                          direccion='Plaza de Armas, Santiago',
                          ciudad='Santiago', telefono='+56 2 2123 4567',
                          correo='demo@reciclaje.cl', activo=True)
        db.session.add(cliente)
        db.session.flush()

    solicitudes = [_crear_ticket_y_solicitud(item, cliente) for item in DATOS_DEMO]

    vehiculo = Vehiculo.query.filter_by(identificador='CAM-01').first()
    if not vehiculo:
        vehiculo = Vehiculo(
            identificador='CAM-01', patente='ABC-123', nombre='Camión 01',
            capacidad=1000, unidad='kg', estado_disponibilidad='disponible',
            perfil_ruteo='driving-hgv',
            lat_inicio=DEPOSITO_DEMO['lat'], lon_inicio=DEPOSITO_DEMO['lon'],
            lat_fin=DEPOSITO_DEMO['lat'], lon_fin=DEPOSITO_DEMO['lon'],
            conductor_id=usuarios['Conductor'].id)
        db.session.add(vehiculo)
        db.session.flush()
        click.echo('> Vehículo demo creado: CAM-01')

    jornada = _crear_jornada(solicitudes, vehiculo, usuarios['Despachador'])
    db.session.commit()
    return jornada, usuarios


def registrar_comandos(app):

    @app.cli.command('seed-routing-demo')
    @with_appcontext
    def seed_routing_demo():
        """Crea datos de demostración del módulo de recolección (idempotente)."""
        jornada, usuarios = ejecutar_seed_demo()
        click.echo('')
        click.echo('Datos de demostración listos:')
        click.echo(f'  Despachador: {usuarios["Despachador"].username}')
        click.echo(f'  Conductor : {usuarios["Conductor"].username}')
        click.echo(f'  Jornada   : {jornada.id} ({jornada.fecha_operacional})')
        click.echo('Ejecute el servidor y abra /recoleccion/planificacion?jornada_id='
                   f'{jornada.id} para planificar.')
