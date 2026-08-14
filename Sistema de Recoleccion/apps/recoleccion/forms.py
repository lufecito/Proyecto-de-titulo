# -*- encoding: utf-8 -*-
"""Formularios del módulo de recolección (Flask-WTF / WTForms)."""

from datetime import datetime

from flask_wtf import FlaskForm
from wtforms import (BooleanField, FloatField, IntegerField, SelectField,
                     SelectMultipleField, StringField, SubmitField)
from wtforms.validators import DataRequired, Length, NumberRange, Optional


def parsear_datetime_local(valor):
    """Convierte 'YYYY-MM-DDTHH:MM' (input datetime-local) a datetime naive."""
    if not valor:
        return None
    valor = valor.strip()
    for formato in ('%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M', '%Y-%m-%dT%H:%M:%S',
                    '%Y-%m-%d'):
        try:
            return datetime.strptime(valor, formato)
        except ValueError:
            continue
    return None


def parsear_float(valor):
    if not valor:
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


class SolicitudRecoleccionForm(FlaskForm):
    ticket_id = SelectField('Ticket', coerce=int, validators=[DataRequired()])
    direccion_original = StringField('Dirección del punto de recolección',
                                     validators=[Length(max=240)])
    direccion_normalizada = StringField('Dirección normalizada',
                                        validators=[Length(max=240)])
    comuna = StringField('Comuna', validators=[Length(max=120)])
    region = StringField('Región', validators=[Length(max=120)])
    referencia = StringField('Referencia', validators=[Length(max=240)])
    latitud = StringField('Latitud')
    longitud = StringField('Longitud')
    demanda = FloatField('Demanda estimada', default=0,
                         validators=[NumberRange(min=0)])
    unidad_demanda = SelectField('Unidad', choices=[('kg', 'kg'), ('unid', 'unidades'),
                                                    ('bolsas', 'bolsas')], default='kg')
    duracion_servicio_seg = IntegerField('Duración de servicio (seg)', default=900,
                                         validators=[NumberRange(min=0)])
    prioridad = SelectField('Prioridad', coerce=int,
                            choices=[(1, '1 - Muy alta'), (2, '2 - Alta'),
                                     (3, '3 - Media'), (4, '4 - Baja')], default=3)
    ventana_inicio = StringField('Ventana inicio (YYYY-MM-DDTHH:MM)',
                                 validators=[Optional()])
    ventana_fin = StringField('Ventana fin (YYYY-MM-DDTHH:MM)',
                              validators=[Optional()])
    enviar = SubmitField('Guardar')


class VehiculoForm(FlaskForm):
    identificador = StringField('Identificador', validators=[DataRequired(),
                                                             Length(max=40)])
    patente = StringField('Patente', validators=[Optional(), Length(max=20)])
    nombre = StringField('Nombre', validators=[DataRequired(), Length(max=120)])
    capacidad = FloatField('Capacidad', default=1000, validators=[NumberRange(min=0)])
    unidad = SelectField('Unidad de capacidad', choices=[('kg', 'kg'), ('m3', 'm3')],
                         default='kg')
    perfil_ruteo = SelectField('Perfil de ruteo',
                               choices=[('driving-hgv', 'driving-hgv'),
                                        ('driving-truck', 'driving-truck'),
                                        ('driving-car', 'driving-car')],
                               default='driving-hgv')
    lat_inicio = StringField('Latitud de inicio')
    lon_inicio = StringField('Longitud de inicio')
    lat_fin = StringField('Latitud de término')
    lon_fin = StringField('Longitud de término')
    conductor_id = SelectField('Conductor', coerce=int, validators=[Optional()])
    estado_disponibilidad = SelectField('Disponibilidad',
                                        choices=[('disponible', 'Disponible'),
                                                 ('no_disponible', 'No disponible')],
                                        default='disponible')
    enviar = SubmitField('Guardar')


class JornadaForm(FlaskForm):
    fecha_operacional = StringField('Fecha operacional (YYYY-MM-DD)',
                                    validators=[DataRequired()])
    inicio_operacion = StringField('Inicio de operación (YYYY-MM-DDTHH:MM)',
                                   validators=[DataRequired()])
    fin_operacion = StringField('Fin de operación (YYYY-MM-DDTHH:MM)',
                                validators=[Optional()])
    deposito_direccion = StringField('Dirección del depósito',
                                     validators=[Length(max=240)])
    deposito_lat = StringField('Latitud del depósito')
    deposito_lon = StringField('Longitud del depósito')
    solicitudes = SelectMultipleField('Solicitudes', coerce=int)
    vehiculos = SelectMultipleField('Vehículos', coerce=int)
    responsable_id = SelectField('Responsable', coerce=int, validators=[Optional()])
    enviar = SubmitField('Guardar')
